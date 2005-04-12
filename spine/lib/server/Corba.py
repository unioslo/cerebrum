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
            return _convert_corba_types_to_none(data_type)
        elif data_type in class_cache:
            return None
    elif data_type in corba_types:
        return obj
    elif isinstance(data_type, Struct):
        data_type = data_type.data_type
        struct = corba_structs[data_type]

        vargs = {}
        vargs['reference'] = convert_to_corba(obj['reference'], transaction, data_type)

        methods = [i for i in data_type.method_slots if not i.write and not i.args]
        for attr in data_type.slots + methods:
            if attr.name in obj:
                value = convert_to_corba(obj[attr.name], transaction, attr.data_type)
                if getattr(attr, 'optional', False):
                    vargs['%s_exists' % attr.name] = True
            else:
                if getattr(attr, 'optional', False):
                    vargs['%s_exists' % attr.name] = False
                value = _convert_corba_types_to_none(attr.data_type)
                if value is None and attr.data_type not in class_cache:
                    raise TypeError("Can't convert attribute %s to none" % attr.name)
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

def _convert_corba_types_to_none(data_type):
    """Returns the value for attr.data_type which is most None."""
    value = None
    if data_type is int:
        value = 0
    elif data_type is str:
        value = ""
    elif data_type is bool:
        value = False
    elif type(data_type) is list:
        value = []
    return value

def _create_corba_method(method):
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

        try:    # Wrap expected exceptions in corba-expcetions.

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

            # Run the real method
            value = getattr(self.spine_object, method.name)(*args, **vargs)

            if method.write:
                self.spine_object.save()

            return convert_to_corba(value, self.transaction, method.data_type)

        except Exception, e:
            import SpineIDL, types, traceback

            if getattr(e, '__class__', e) not in method.exceptions:
                
                #temp throw unknown exceptions to the client.
                #remember to remove this, and in Builder.py before production.
                name = getattr(e, '__class__',str(e))
                traceback.print_exc()
                exception_string = "Unknown error '%s':\n%s\n%s" % (
                                    name, str(e.args), 
                                    ''.join(traceback.format_exception(sys.exc_type, 
                                        sys.exc_value,
                                        sys.exc_traceback)))
                raise SpineIDL.Errors.DebugException(exception_string)
                #raise

            if len(e.args) > 0 and type(e.args[0]) is str:
                explanation = e.args[0]
            else:
                explanation = ""
            
            exception = getattr(SpineIDL.Errors, e.__class__.__name__)
            exception = exception(explanation)
             
            raise exception

    return corba_method

def _create_idl_comment(comment='', args=(), rtn_type='', exceptions=(), tabs=0):
    """Returns a string with the idl comment.

    Returns a comment on the following syntax:
    /**
    * comment
    * \\param argument argument type
    * \\return Returns a rtn_type
    * \\exception Exception
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
        txt += '%s* \\exception %s\n' % (tabs, i.__name__)
    txt += '%s*/\n' % tabs
    return txt

def _trim_docstring(docstring):
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

def _create_idl_interface(cls, error_module="", docs=False):
    """Create idl definition for the class 'cls'.
    
    Creates idl interface for the class from attributes in cls.slots
    and methods in cls.method_slots.

    If you wish the idl to be commented, use docs=True. This will copy
    the docstring into the idl interface for this class.
    """
    def get_exceptions(exceptions, module=""):
        """Return the corba-string with exceptions."""
        if not exceptions:
            return ''
        else:
            if module:
                module += '::'
            spam = ['%s%s' % (module, i.__name__) for i in exceptions]
            return '\n\t\traises(%s)' % ', '.join(spam)

    def get_type(data_type):
        """Return a string, corba can understand, representing the data_type."""
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

    def add_header(header):
        if header not in headers:
            headers.append(header)

    txt = ""
    headers = []
    exceptions_headers = []
    
    if docs and cls.__doc__:
        txt += _create_idl_comment(_trim_docstring(cls.__doc__))
    
    txt += 'interface Spine%s' % cls.__name__

    #Inheritage
    parent_slots = sets.Set()
    if cls.builder_parents:
        spam = sets.Set(cls.builder_parents)
        txt += ': ' + ', '.join(['Spine' + i.__name__ for i in spam])
        for i in cls.builder_parents:
            parent_slots.update(i.slots)
            parent_slots.update(i.method_slots)

    txt += ' {\n'

    # Attributes
    if docs and cls.slots:
        txt += '\t//Get and set methods for attributes\n'
    for attr in cls.slots:
        if attr in parent_slots:
            continue

        exceptions_headers.extend(attr.exceptions)
        excp = get_exceptions(attr.exceptions, error_module)

        data_type = get_type(attr.data_type)

        if docs:
            txt += _create_idl_comment('', (), data_type, attr.exceptions, 1)

        txt += '\t%s get_%s()%s;\n' % (data_type, attr.name, excp)
        txt += '\n'

        if attr.write:
            args = ((attr.name, attr.data_type),)
            if docs:
                txt += _create_idl_comment('', args, 'void', attr.exceptions, 1)
            txt += '\tvoid set_%s(in %s new_%s)%s;\n' % (attr.name, data_type, attr.name, excp)
            txt += '\n'

    # Methods
    if docs and cls.slots and cls.method_slots:
        txt += '\t//Other methods\n'
    for method in cls.method_slots:
        if method in parent_slots:
            continue

        args = []
        for name, data_type in method.args:
            args.append('in %s in_%s' % (get_type(data_type), name))

        data_type = get_type(method.data_type)
        
        exceptions_headers.extend(method.exceptions)
        excp = get_exceptions(method.exceptions, error_module)

        if method.doc is None and hasattr(cls, method.name):
            method.doc = getattr(cls, method.name).__doc__
        doc = _trim_docstring(method.doc or '')
        
        if docs:
            txt += _create_idl_comment(doc, method.args, data_type, method.exceptions, 1)

        txt += '\t%s %s(%s)%s;\n' % (data_type, method.name, ', '.join(args), excp)
        txt += '\n'

    txt += '};\n'
    
    return headers, exceptions_headers, txt

def _create_idl_exceptions(exceptions, docs=False):
    """Creates a Error module for the exceptions."""
    txt = 'module Errors {\n'
    for i in exceptions:
        if docs:
            txt += '\t/**\n'
            if i.__doc__:
                txt += '\t* %s\n' % i.__doc__
            txt += '\t* \\param explanation A string containing a short explanation.\n' 
            txt += '\t*/\n'
        txt += '\texception %s{ \n\t\tstring explanation;\n\t};\n\n' % i.__name__
    txt += '};'
    return txt

def create_idl_source(classes, module_name='Generated', docs=False):
    """Create idl for classes in 'classes'.

    Creates the idl source for the classes in 'classes' under the
    module name 'module_name'.

    If you wish the idl to be commented, use docs=True. This will copy
    the docstring into the idl.
    """
    # Prepare headers, exceptions and lines for all classes.
    headers = []        # contains headers for all classes.
    exceptions = []     # contains exceptions for the module.
    lines = []          # contains interface definitions for all classes.
    
    for cls in classes:
        values = _create_idl_interface(cls, '%s::Errors' % module_name, docs)
        cls_headers, cls_exceptions, cls_txt = values
        for i in cls_headers:
            if i not in headers:
                headers.append(i)
        for i in cls_exceptions:
            if i not in exceptions:
                exceptions.append(i)
        lines.append(cls_txt)

    # Build the idl string 'txt'.
    txt = 'module %s {\n\t' % module_name
    txt += '\n'.join(headers).replace('\n', '\n\t')
    if exceptions:
        txt += '\n\n\t'
        txt += _create_idl_exceptions(exceptions, docs).replace('\n', '\n\t')
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
        get = Method(get_name, attr.data_type, exceptions=attr.exceptions)

        setattr(corba_class, get_name, _create_corba_method(get))

        if attr.write:
            set_name = 'set_' + attr.name
            set = Method(set_name, None, [(attr.name, attr.data_type)],
                         exceptions=attr.exceptions, write=True)

            setattr(corba_class, set_name, _create_corba_method(set))

    for method in cls.method_slots:
        setattr(corba_class, method.name, _create_corba_method(method))

    class_cache[cls] = corba_class

# arch-tag: d64745f8-6ea2-469e-b821-b0f448ab7e4a
