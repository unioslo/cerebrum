# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

import Communication

from Cerebrum.extlib import sets
from Cerebrum.spine.SpineLib.Builder import Method
from Cerebrum.spine.SpineLib.DumpClass import Struct, DumpClass
from Cerebrum.spine.SpineLib.SearchClass import SearchClass
from Cerebrum.spine.Auth import AuthOperationType

# FIXME: weakref her?
class_cache = {}
object_cache = {}

corba_types = [int, str, bool, None]
corba_structs = {}

def convert_to_corba(obj, transaction, data_type):
    if obj is None and data_type is not None:
        if data_type in corba_types:
            raise TypeError("Can't convert None, should be %s" % data_type)
        elif data_type in class_cache:
            return None
    elif data_type in corba_types:
        return obj
    elif isinstance(data_type, Struct):
        data_type = data_type.data_type
        struct = corba_structs[data_type]

        vargs = {}
        vargs['reference'] = convert_to_corba(obj['reference'], transaction, data_type)

        for attr in data_type.slots + [i for i in data_type.method_slots if not i.write]:
            if attr.name in obj:
                value = convert_to_corba(obj[attr.name], transaction, attr.data_type)
            else:
                if attr.data_type == int:
                    value = 0
                elif attr.data_type == str:
                    value = ''
                elif attr.data_type == bool:
                    value = False
                elif type(attr.data_type) == list:
                    value = []
                elif attr.data_type in class_cache:
                    value = None
                else:
                    raise TypeError("Can't convert attribute %s in %s to nil" % (attr, data_type))
            vargs[attr.name] = value

        return struct(**vargs)

    elif type(data_type) == list:
        return [convert_to_corba(i, transaction, data_type[0]) for i in obj]

    elif data_type in class_cache:
        # corba casting
        if obj.__class__ in data_type.builder_children:
            data_type = obj.__class__

        corba_class = class_cache[data_type]
        key = (corba_class, transaction, obj)
        if key in object_cache:
            return object_cache[key]

        com = Communication.get_communication()
        corba_object = com.servant_to_reference(corba_class(obj, transaction))
        object_cache[key] = corba_object
        return corba_object
    else:
        raise TypeError('unknown data_type', data_type)

def convert_from_corba(obj, data_type):
    if data_type in corba_types:
        return obj
    elif type(data_type) == list:
        return [convert_from_corba(i, data_type[0]) for i in obj]
    elif data_type in class_cache:
        corba_class = class_cache[data_type]
        com = Communication.get_communication()
        return com.reference_to_servant(obj).spine_object

def create_corba_method(method):
    args_table = {}
    for name, data_type in method.args:
        args_table[name] = data_type
        
    def corba_method(self, *corba_args, **corba_vargs):
        if len(corba_args) + len(corba_vargs) > len(args_table):
            raise TypeError('too many arguments')

        # Auth

        class_name = self.spine_class.__name__
        if self.transaction is not None:
            operator = self.transaction.get_client()
        else:
            operator = None
        operation_name = '%s.%s' % (class_name, method.name)
        try:
            operation_type = AuthOperationType(name=operation_name)
        except Exception, e:
            # FIXME: kaste en exception
            # print 'no operation_type defined for %s' % operation_name
            operation_type = None

        # FIXME: bruk isinstance eller issubclass
        if operator is not None and hasattr(self.spine_object, 'check_permission'):
            if self.spine_object.check_permission(operator, operation_type):
                print operation_name, 'access granted'
            else:
                # FIXME: kaste en exception
                # print operation_name, 'access denied' 
                pass
        else:
            # FIXME: kaste en exception
            pass

        # Transaction

        if hasattr(self.transaction, 'snapshot'):
            if isinstance(self.spine_object, DumpClass) or isinstance(self.spine_object, SearchClass):
                self.spine_object.cache = self.transaction.snapshot
            elif method.write:
                raise Exception('Trying to access write-method outside a transaction: %s' % method)
            else:
                cache = self.transaction.snapshot
                key = self.spine_object.get_primary_key()
                self.spine_object = self.spine_class(*key, **{'cache':cache})
        else:
            self.transaction.add_ref(self.spine_object)

        if method.write:
            self.spine_object.lock_for_writing(self.transaction)
        else:
            self.spine_object.lock_for_reading(self.transaction)

        # convert corba arguments to real arguments
        args = []
        for value, (name, data_type) in zip(corba_args, method.args):
            args.append(convert_from_corba(value, data_type))

        vargs = {}
        for name, value in corba_vargs:
            data_type = args_table[name]
            vargs[name] = convert_from_corba(value, data_type)

        # run the real method
        value = getattr(self.spine_object, method.name)(*args, **vargs)
        if method.write:
            self.spine_object.save()

        return convert_to_corba(value, self.transaction, method.data_type)

    return corba_method

def create_idl_interface(cls, exceptions=()):
    txt = 'interface Spine%s' % cls.__name__

    parent_slots = sets.Set()
    if cls.builder_parents:
        txt += ': ' + ', '.join(['Spine' + i.__name__ for i in sets.Set(cls.builder_parents)])
        for i in cls.builder_parents:
            parent_slots.update(i.slots)
            parent_slots.update(i.method_slots)

    txt += ' {\n'

    def get_exceptions(exceptions):
        # FIXME: hente ut navnerom fra cereconf? err.. stygt :/
        if not exceptions:
            return ''
        else:
            return '\n\t\traises(%s)' % ', '.join(['Cerebrum_core::Errors::' + i for i in exceptions])

    headers = []
    def add_header(header):
        if header not in headers:
            headers.append(header)
    def get_type(data_type):
        if type(data_type) == list:
            blipp = get_type(data_type[0])
            name = blipp + 'Seq'
            add_header('typedef sequence<%s> %s;' % (blipp, name))

        elif data_type == str:
            name = 'string'

        elif data_type == int:
            name = 'long'

        elif data_type == None:
            name = 'void'

        elif data_type == bool:
            name = 'boolean'

        elif isinstance(data_type, Struct):
            cls = data_type.data_type
            name = cls.__name__ + 'Struct'

            header = 'struct %s {\n' % name
            header += '\t%s reference;\n' % get_type(cls)
            for attr in cls.slots + [i for i in cls.method_slots if not i.write]:
                header += '\t%s %s;\n' % (get_type(attr.data_type), attr.name)

            header += '};'

            add_header(header)

        else:
            name = 'Spine' + data_type.__name__
            add_header('interface %s;' % name)

        return name
            

    txt += '\n\t//get and set methods for attributes\n'
    for attr in cls.slots:
        if attr in parent_slots:
            continue
        exception = get_exceptions(tuple(attr.exceptions) + tuple(exceptions))
        data_type = get_type(attr.data_type)
        txt += '\t%s get_%s()%s;\n' % (data_type, attr.name, exception)
        if attr.write:
            txt += '\tvoid set_%s(in %s new_%s)%s;\n' % (attr.name, data_type, attr.name, exception)
        txt += '\n'

    if cls.method_slots:
        txt += '\n\t//other methods\n'
    for method in cls.method_slots:
        if method in parent_slots:
            continue
        exception = get_exceptions(tuple(method.exceptions) + tuple(exceptions))

        args = []
        for name, data_type in method.args:
            args.append('in %s in_%s' % (get_type(data_type), name))

        data_type = get_type(method.data_type)
        txt += '\t%s %s(%s)%s;\n' % (data_type, method.name, ', '.join(args), exception)

    txt += '};\n'

    return headers, txt

def create_idl_source(classes, module_name='Generated'):
    include = '#include "errors.idl"\n'
    headers = []
    lines = []

    exceptions = ('TransactionError', 'AlreadyLockedError')

    defined = []
    for cls in classes:
        cls_headers, cls_txt = create_idl_interface(cls, exceptions=exceptions)
        for i in cls_headers:
            if i not in headers:
                headers.append(i)
        lines.append('\t' + cls_txt.replace('\n', '\n\t'))

    return '%s\nmodule %s {\n%s\n%s\n};\n' % (include, module_name,
                                              '\n'.join(headers), '\n'.join(lines))

class CorbaClass:
    def __init__(self, spine_object, transaction):
        self.spine_object = spine_object
        self.transaction = transaction

def register_spine_class(cls, idl_cls, idl_struct):
    name = cls.__name__
    corba_class_name = 'Spine' + name

    corba_structs[cls] = idl_struct

    exec 'class %s(CorbaClass, idl_cls):\n\tpass\ncorba_class = %s' % (
        corba_class_name, corba_class_name)

    corba_class.spine_class = cls

    for attr in cls.slots:
        get_name = 'get_' + attr.name
        get = Method(get_name, attr.data_type)

        setattr(corba_class, get_name, create_corba_method(get))

        if attr.write:
            set_name = 'set_' + attr.name
            set = Method(set_name, None, [(attr.name, attr.data_type)], write=True)

            setattr(corba_class, set_name, create_corba_method(set))

    for method in cls.method_slots:
        setattr(corba_class, method.name, create_corba_method(method))

    class_cache[cls] = corba_class

# arch-tag: d64745f8-6ea2-469e-b821-b0f448ab7e4a
