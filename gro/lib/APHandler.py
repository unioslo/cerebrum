# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

import omniORB

from Cerebrum_core import Errors
from Transaction import Transaction

import Communication

import classes.Registry
registry = classes.Registry.get_registry()

CorbaBuilder = registry.CorbaBuilder
Method = registry.Method
Attribute = registry.Attribute

def create_ap_method(class_name, method_name, data_type, write, method_arguments):
    args_table = dict(method_arguments)
    def method(self, *corba_args, **corba_vargs):
        if len(corba_args) + len(corba_vargs) > len(method_arguments):
            raise TypeError('too many arguments')

        # Auth
        operation_type = registry.AuthOperationType('%s.%s' % (class_name, method_name))
        operator = self.ap_handler.client
        try:
            if self.gro_object.check_permission(operator, operation_type):
                print 'access granted'
            else:
                print 'access denied'
        except Exception, e:
            print 'warning check_permission(', operator , ', ', operation_type, ') failed:', e
            print 'access denied'

        # Transaction
        if self.ap_handler.transaction_started:
            if write:
                self.gro_object.lock_for_writing(self.ap_handler)
            else:
                self.gro_object.lock_for_reading(self.ap_handler)

            self.ap_handler.add_ref(self.gro_object)
        elif write:
            raise Errors.TransactionError('No transaction started')
        else:
            # no transaction, so we need to check for writelock
            writelock_holder = self.gro_object.get_writelock_holder()
            if writelock_holder is not None: # if there is a writelock, we need to return a fresh object
                new = self.gro_object.__class__(nocache=True, *self.gro_object.get_primary_key())
                self.gro_object = new

        # convert corba arguments to real arguments
        args = []
        for value, arg in zip(corba_args, method_arguments):
            args.append(APHandler.convert_from_corba(value, arg[1]))

        vargs = {}
        for name, value in corba_vargs.items():
            vargs[name] = APHandler.convert_from_corba(value, args_table[name])

        # run the real method
        value = getattr(self.gro_object, method_name)(*args, **vargs)
        if write:
            self.gro_object.save()

        return APHandler.convert_to_corba(value, data_type, self.ap_handler)
    return method

class APClass:
    """ Creator of Access point proxy object.

    An APClass object contains the APHandler and an object from the GRO API. 
    It acts as a proxy for the object.
    This is to give us a sort of automatic session handling that will solve two problems:
    1 - The client does not have to deal with a session id
    2 - GRO can perform locking on objects requested by a client,
        using the APHandler to identify it.
    """

    def __init__(self, gro_object, ap_handler):
        self.gro_object = gro_object
        self.ap_handler = ap_handler

    def create_ap_class(cls, gro_class, idl_class):
        class_name = gro_class.__name__
        ap_class_name = 'AP' + class_name
        
        exec 'class %s(cls, idl_class):\n\tpass\nap_class = %s' % (
             ap_class_name, ap_class_name)

        for attribute in gro_class.slots:
            get_name = 'get_' + attribute.name
            get = create_ap_method(class_name, get_name, attribute.data_type, False, [])
            setattr(ap_class, get_name, get)

            if attribute.write:
                set_name = 'set_' + attribute.name
                set = create_ap_method(class_name, set_name, 'void', True, [(attribute.name, attribute.data_type)])
                setattr(ap_class, set_name, set)

        for method in gro_class.method_slots:
            ap_method = create_ap_method(class_name, method.name, method.data_type, method.write, method.args)
            setattr(ap_class, method.name, ap_method)

        ap_class.gro_class = gro_class

        return ap_class

    create_ap_class = classmethod(create_ap_class)

def create_ap_handler_get_method(data_type):
    def get(self, *args, **vargs):
        if not self.transaction_started:
            self.transaction_disabled = True
        obj = APHandler.gro_classes[data_type](*args, **vargs)
        return APHandler.convert_to_corba(obj, data_type, self)
    return get

class APHandler(CorbaBuilder, Transaction):
    # FIXME: skriv om denne
    """Access point handler.

    Each client has his own access point, wich will be used to identify the client
    so we can lock down objects to the client and check if the client has access to
    make the changes he tries to do. The client has to provide GRO a username
    and password before he gets the APHandler. This information will be stored in
    this object.
    """

    classes = {} # Access Point classes
    gro_classes = {} # GRO API classes to be used
    slots = []
    method_slots = [Method('begin','APHandler'), Method('rollback', 'void'), Method('commit', 'void')]

    def convert_to_corba(cls, value, data_type, ap_handler):
        if data_type == 'Entity': # we need to "cast" to the correct class
            data_type = value.__class__.__name__

        # TODO: skummel bruk av navnekonvesjon, burde legge til flags i Attribute i stedet
        if data_type.endswith('Seq'):
            return [cls.convert_to_corba(i, data_type[:-3], ap_handler) for i in value]

        elif data_type in cls.classes:
            ap_object = cls.classes[data_type](value, ap_handler)
            com = Communication.get_communication()
            return com.servant_to_reference(ap_object)

        elif data_type == 'void':
            return value

        elif value is None:
            # TODO. her må vi bestemme oss for noe. lage en egen exception for dette kanskje,
            # siden det verdier faktisk kan være None
            print 'warning. trying to return None'
            raise TypeError('cant convert None')

        else:
            return value

    convert_to_corba = classmethod(convert_to_corba)

    def convert_from_corba(cls, value, data_type):
        if data_type.endswith('Seq'):
            return [cls.convert_from_corba(i, data_type[:-3]) for i in value]
        elif data_type in cls.classes:
            com = Communication.get_communication()
            return com.reference_to_servant(value).gro_object
        else:
            return value

    convert_from_corba = classmethod(convert_from_corba)

    def register_gro_class(cls, gro_class):
        gro_class.build_methods()
        name = gro_class.__name__

        method_name = 'get'
        for i in name:
            if i.isupper():
                method_name += '_' + i.lower()
            else:
                method_name += i
        method_impl = create_ap_handler_get_method(name)
        method = Method(method_name, name, [(i.name, i.data_type) for i in gro_class.primary])

        cls.method_slots.append(method)
        cls.gro_classes[name] = gro_class
        setattr(cls, method_name, method_impl)

    register_gro_class = classmethod(register_gro_class)

    def create_idl(cls):
        include = '#include "errors.idl"\n'
        txt = 'typedef sequence<string> stringSeq;\n'
        txt += 'typedef sequence<long> longSeq;\n'
        txt += 'typedef sequence<float> floatSeq;\n'
        txt += 'typedef sequence<boolean> booleanSeq;\n'

        exceptions = ('TransactionError', 'AlreadyLockedError')

        defined = []
        for gro_class in cls.gro_classes.values():
            txt += gro_class.create_idl_header(defined)
            
        for gro_class in cls.gro_classes.values():
            txt += gro_class.create_idl_interface(exceptions=exceptions)

        tmp = cls.create_idl_interface(exceptions=exceptions)
        txt += tmp
        
        return '%s\nmodule %s {\n\t%s\n};\n' % (include, 'generated', txt.replace('\n', '\n\t'))

    create_idl = classmethod(create_idl)

    def build_classes(cls):
        idl_string = cls.create_idl()
        # FIXME
        omniORB.importIDLString(idl_string, ['-I/home/erikgors/cvs/cerebrum/gro/lib/idl'])
        import generated__POA
        for name, gro_class in cls.gro_classes.items():
            idl_class = getattr(generated__POA, name)
            ap_class = APClass.create_ap_class(gro_class, idl_class)
            cls.classes[name] = ap_class

    build_classes = classmethod(build_classes)

    def create_ap_handler_impl(cls):
        import generated__POA
        class APHandler(cls, generated__POA.APHandler):
            pass
        return APHandler

    create_ap_handler_impl = classmethod(create_ap_handler_impl)

    def begin(self):
        ap = self.__class__(self.client)
        Transaction.begin(ap)
        com = Communication.get_communication()
        return com.servant_to_reference(ap)

_ap_handler_class = None
_is_built = None

def build_ap_handler():
    global _is_built
    if _is_built is None:
        for cls in registry.get_gro_classes().values():
            APHandler.register_gro_class(cls)

def get_ap_handler_class():
    global _ap_handler_class
    build_ap_handler()
    if _ap_handler_class is None:
        APHandler.build_classes()
        _ap_handler_class = APHandler.create_ap_handler_impl()
    return _ap_handler_class

# arch-tag: 2625e142-6958-4544-96bc-e062dfe7565a
