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

"""
This module handles everything related to the middleway, corba, in Spine.

Public functions:
- convert_to_corba      converts a python object into a corba object.
- convert_from_corba    converts a corba object into a python object.
- create_idl_source     creates the idl string for the given classes.
- register_spine_class  creates corbaclass and registers the class.
"""

import sys
import Communication

from Cerebrum.extlib import sets
from Cerebrum.spine.SpineLib.Builder import Method
from Cerebrum.spine.SpineLib.DumpClass import Struct, DumpClass
from Cerebrum.spine.SpineLib.SearchClass import SearchClass
from Cerebrum.spine.Auth import AuthOperationType

__all__ = ['convert_to_corba', 'convert_from_corba',
           'create_idl_source', 'register_spine_class']

# FIXME: weakref her?
class_cache = {}
object_cache = {}

corba_types = [int, str, bool, None]
corba_structs = {}

def convert_to_corba(obj, transaction, data_type):
    """Convert obj to a data type corba knows of."""
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

        for attr in data_type.slots + [i for i in data_type.method_slots if not i.write and not i.args]:
            if attr.name in obj:
                value = convert_to_corba(obj[attr.name], transaction, attr.data_type)
                if getattr(attr, 'optional', False):
                    vargs['%s_exists' % attr.name] = True
            else:
                if getattr(attr, 'optional', False):
                    vargs['%s_exists' % attr.name] = False
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
    """Convert a corba-object to a python object."""
    if data_type in corba_types:
        return obj
    elif type(data_type) == list:
        return [convert_from_corba(i, data_type[0]) for i in obj]
    elif data_type in class_cache:
        corba_class = class_cache[data_type]
        com = Communication.get_communication()
        return com.reference_to_servant(obj).spine_object

def create_corba_method(method):
    """Creates a wrapper for method.

    Creates a corbamethod which wraps the method 'method'.
    The wrapper handles authentication, and converts arguments
    from corbaobjects to pythonobjects.
    """
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

def create_idl_comment(comment='', args=(), rtn_type='', exceptions=(), tabs=0):
    """Returns a string with the idl comment.

    Returns a comment on the following syntax:
    /**
    * comment
    * \\param argument argument type
    * \\return Returns a rtn_type
    * \\throw Exception
    */

    If you need the comment to be indented, give the number of tabs
    with 'tabs'.
    """
    tabs = '\t'*tabs
    txt = '%s/**\n' % tabs
    if comment:
        comment = comment.replace('\n', '\n%s* ' % tabs)
        txt += '%s* %s\n' % (tabs, comment)
    for name, arg_type in args:
        spam = 'value of type'
        if type(arg_type) in (list, tuple):
            arg_type, = arg_type
            spam = 'list of types'
        value = getattr(arg_type, '__name__', str(arg_type))
        txt += '%s* \\param %s %s %s\n' % (tabs, name, spam, value)
    if rtn_type:
        txt += '%s* \\return value of type %s\n' % (tabs, rtn_type)
    for i in exceptions:
        txt += '%s* \\throw %s\n' % (tabs, i)
    txt += '%s*/\n' % tabs
    return txt

def trim_docstring(docstring):
    """Trims indentation from docstrings.

    This method is copied from pep 257 regarding docstrings. It was
    placed in public domain by David Goodger & Guido van Rossum, which
    can be found here: http://www.python.org/peps/pep-0257.html
    """
    if not docstring:
        return ''
    # Convert tabs to spaces (following the normal Python rules)
    # and split into a list of lines:
    lines = docstring.expandtabs().splitlines()
    # Determine minimum indentation (first line doesn't count):
    indent = sys.maxint
    for line in lines[1:]:
        stripped = line.lstrip()
        if stripped:
            indent = min(indent, len(line) - len(stripped))
    # Remove indentation (first line is special):
    trimmed = [lines[0].strip()]
    if indent < sys.maxint:
        for line in lines[1:]:
            trimmed.append(line[indent:].rstrip())
    # Strip off trailing and leading blank lines:
    while trimmed and not trimmed[-1]:
        trimmed.pop()
    while trimmed and not trimmed[0]:
        trimmed.pop(0)
    # Return a single string:
    return '\n'.join(trimmed)

def create_idl_interface(cls, exceptions=(), docs=False):
    """Create idl definition for the class 'cls'.
    
    Creates idl interface for the class from attributes in cls.slots
    and methods in cls.method_slots.

    'exceptions' takes a list of strings, with the name of exceptions
    which can be raised by all the methods in the class 'cls'.
    
    If you wish the idl to be commented, use docs=True. This will copy
    the docstring into the idl interface for this class.
    """
    txt = ""
    
    if docs and cls.__doc__:
        txt += create_idl_comment(trim_docstring(cls.__doc__))
    
    txt += 'interface Spine%s' % cls.__name__

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

            for attr in cls.slots:
                header += '\t%s %s;\n' % (get_type(attr.data_type), attr.name)
                if attr.optional:
                    header += '\tboolean %s_exists;\n' % attr.name

            for method in cls.method_slots:
                if method.write or method.args:
                    continue
                header += '\t%s %s;\n' % (get_type(method.data_type), method.name)

            header += '};'

            add_header(header)
        else:
            name = 'Spine' + data_type.__name__
            add_header('interface %s;' % name)
        return name

    if docs and cls.slots:
        txt += '\t//Get and set methods for attributes\n'
    for attr in cls.slots:
        if attr in parent_slots:
            continue

        exceptions = tuple(attr.exceptions) + tuple(exceptions)
        exception = get_exceptions(exceptions)
        data_type = get_type(attr.data_type)
        
        txt += create_idl_comment('', (), data_type, exceptions, tabs=1)
        txt += '\t%s get_%s()%s;\n' % (data_type, attr.name, exception)
        txt += '\n'

        if attr.write:
            args = ((attr.name, attr.data_type),)
            txt += create_idl_comment('', args, 'void', exceptions, tabs=1)
            txt += '\tvoid set_%s(in %s new_%s)%s;\n' % (attr.name, data_type, attr.name, exception)
            txt += '\n'

    if docs and cls.slots and cls.method_slots:
        txt += '\t//Other methods\n'
    for method in cls.method_slots:
        if method in parent_slots:
            continue

        args = []
        for name, data_type in method.args:
            args.append('in %s in_%s' % (get_type(data_type), name))
        data_type = get_type(method.data_type)
        exception = tuple(method.exceptions) + tuple(exceptions)

        if method.doc is None and hasattr(cls, method.name):
            method.doc = getattr(cls, method.name).__doc__
        
        doc = trim_docstring(method.doc or '')
        txt += create_idl_comment(doc, method.args, data_type, exception, tabs=1)

        exception = get_exceptions(exception)
        txt += '\t%s %s(%s)%s;\n' % (data_type, method.name, ', '.join(args), exception)
        txt += '\n'

    txt += '};\n'
    return headers, txt

def create_idl_source(classes, module_name='Generated', docs=False):
    """Create idl for classes in 'classes'.

    Creates the idl source for the classes in 'classes' under the
    module name 'module_name'.

    If you wish the idl to be commented, use docs=True. This will copy
    the docstring into the idl.
    """
    include = '#include "errors.idl"'
    global_exceptions = ()

    # Prepare headers and lines for all classes.
    headers = []   # contains headers for all classes.
    lines = []     # contains interface definitions for all classes.
    for cls in classes:
        cls_headers, cls_txt = create_idl_interface(cls, global_exceptions, docs)
        for i in cls_headers:
            if i not in headers:
                headers.append(i)
        lines.append(cls_txt)

    # Build the idl string 'txt'.
    txt = '%s\n\nmodule %s {\n\t' % (include, module_name)
    txt += '\n'.join(headers).replace('\n', '\n\t')
    txt += '\n\n\t'
    txt += '\n'.join(lines).replace('\n', '\n\t')
    txt += '\n};\n'
    return txt

class CorbaClass:
    """Base class for all corba-classes.

    All classes we are gonna send to clients through corba will inherit
    from this class.
    """
    
    def __init__(self, spine_object, transaction):
        self.spine_object = spine_object
        self.transaction = transaction

def register_spine_class(cls, idl_cls, idl_struct):
    """Create corba for the class 'cls'.

    Registers structs and classes in corba_structs and class_cache.
    Creates a corbaclass for the class, and builds corbamethods in it.
    """
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
