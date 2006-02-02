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
This module handles everything related to the middleware, CORBA, in Spine.
"""

import sys
import threading
import traceback
import weakref

import cereconf
import Communication

from Cerebrum.extlib import sets
from Cerebrum.spine.SpineLib.Builder import Method
from Cerebrum.spine.SpineLib.Date import Date
from Cerebrum.spine.SpineLib.DumpClass import Struct, Any, DumpClass
from Cerebrum.spine.SpineLib.Locking import Locking
from Cerebrum.spine.SpineLib.Caching import Caching
from Cerebrum.spine.SpineLib.DatabaseClass import DatabaseTransactionClass
from Cerebrum.spine.SpineLib.SearchClass import SearchClass
from Cerebrum.spine.SpineLib.SpineExceptions import AccessDeniedError, ServerProgrammingError, TransactionError, ObjectDeletedError

__all__ = ['convert_to_corba', 'convert_from_corba',
           'create_idl_source', 'register_spine_class','drop_associated_objects']

class_cache = {}
object_cache = {}

corba_types = [int, float, str, bool, None]
corba_structs = {}

object_cache_lock = threading.RLock()

def invalidate_reference(reference):
    object_cache_lock.acquire()
    try:
        try:
            com = Communication.get_communication()
            com.remove_reference(reference)
        except:
            print 'DEBUG: Unable to remove reference when dropping from object cache!'
            traceback.print_exc() # TODO: Log this
    finally:
        object_cache_lock.release()

def invalidate_corba_object(corba_obj):
    object_cache_lock.acquire()
    try:
        key = (corba_obj.get_transaction(), corba_obj.spine_object)
        reference = object_cache[key]
        invalidate_reference(reference)
        del object_cache[key]
    finally:
        object_cache_lock.release()

# FIXME: We should instead organize object_cache with key == transcation.
#        This will be too slow and add unnecessary latency when we have many
#        short lived transactions.
def drop_associated_objects(transaction):
    """Removes all objects associated with the given transaction from the object cache."""
    object_cache_lock.acquire()
    try:
        for key, value in object_cache.items():
            if key[0] == transaction:
                invalidate_reference(value)
            del object_cache[key]
    finally:
        object_cache_lock.release()

def convert_to_corba(obj, transaction, data_type):
    """Convert object 'obj' to a data type CORBA knows."""
    if obj is None and data_type is not None:
        if data_type in corba_types:
            return _convert_corba_types_to_none(data_type)
        elif data_type in class_cache:
            return None
    elif data_type in corba_types:
        if data_type is str:
            return _string_from_db(obj, transaction.get_encoding())
        return obj
    elif isinstance(data_type, Struct):
        data_type = data_type.data_type
        struct = corba_structs[data_type]

        vargs = {}
        for attr in data_type.slots:
            if attr.name in obj:
                if attr.data_type == Date:
                    value = str(obj[attr.name])
                else:
                    value = convert_to_corba(obj[attr.name], transaction, attr.data_type)
                if getattr(attr, 'optional', False):
                    vargs['%s_exists' % attr.name] = True
            else:
                if getattr(attr, 'optional', False):
                    vargs['%s_exists' % attr.name] = False
                if attr.data_type == Date:
                    value = ''
                else:
                    value = _convert_corba_types_to_none(attr.data_type)
                if value is None and attr.data_type not in class_cache:
                    raise ServerProgrammingError("Can't convert attribute %s to None" % attr.name)
            vargs[attr.name] = value

        return struct(**vargs)

    elif type(data_type) == list:
        try:
            return [convert_to_corba(i, transaction, data_type[0]) for i in obj]
        except TypeError:
            traceback.print_exc()
            raise ServerProgrammingError('Unable to convert object %s to CORBA; object is not a list.' % (obj.__class__.__name__))

    elif data_type in class_cache:
        # corba casting
        if obj.__class__ in data_type.builder_children:
            data_type = obj.__class__

        corba_class = class_cache[data_type]
        key = (transaction, obj)
        
        object_cache_lock.acquire()
        try:
            if key in object_cache:
                return object_cache[key]
            else:
                com = Communication.get_communication()
                corba_object = com.servant_to_reference(corba_class(obj, transaction))
                object_cache[key] = corba_object
                return corba_object
        finally:
            object_cache_lock.release()
    elif data_type == Any:
        import omniORB.any
        return omniORB.any.to_any(obj)
    else:
        raise ServerProgrammingError('Cannot convert to CORBA type; unknown data type.', data_type)

def convert_from_corba(obj, data_type):
    """Convert a CORBA object to a python object."""
    if data_type in corba_types:
        return obj
    elif type(data_type) == list:
        return [convert_from_corba(i, data_type[0]) for i in obj]
    elif obj is None:
        return None
    elif data_type in class_cache:
        corba_class = class_cache[data_type]
        com = Communication.get_communication()
        return com.reference_to_servant(obj).spine_object
    elif data_type == Any:
        import omniORB.any
        return omniORB.any.from_any(obj)
    else:
        raise ServerProgrammingError('Cannot convert from CORBA type; unknown data type.', data_type)

def _convert_corba_types_to_none(data_type):
    """Returns the value for data_type which is most like None."""
    value = None
    if data_type is int:
        value = -1
    elif data_type is str:
        value = ""
    elif data_type is bool:
        value = False
    elif data_type is float:
        value = -1.0
    elif type(data_type) is list:
        value = []
    return value

def _string_from_db(str, encoding):
    """
    Converts a string from the database string encoding to the clients
    string encoding.
    """
    if encoding == cereconf.SPINE_DATABASE_ENCODING:
        return str
    return str.decode(cereconf.SPINE_DATABASE_ENCODING).encode(encoding)

def _string_to_db(str, encoding):
    """
    Converts a string from the clients string encoding to the database string
    encoding.
    """
    if encoding == cereconf.SPINE_DATABASE_ENCODING:
        return str
    return str.decode(encoding).encode(cereconf.SPINE_DATABASE_ENCODING)

def _create_corba_method(method):
    """
    Creates a wrapper for the given method. 
    The supplied argument 'method' must be an instance of Builder.Method.

    The generated wrapper method does the following in addition to calling the
    real method in the server-side class:
        1. Check the transaction making the call for lost locks
        2. Authorization
        3. Lock the object if necesseary
        4. Argument conversion from CORBA to python
        5. Calling the method
        6. Argument conversion from python to CORBA

    In addition, the method wraps all exceptions and raise them as proper CORBA exceptions.
    """
    args_table = {}
    for name, data_type in method.args:
        args_table[name] = data_type
        
    def corba_method(self, *corba_args, **corba_vargs):
        assert len(corba_args) + len(corba_vargs) <= len(args_table)

        # This try block is here so we can wrap expected exceptions as CORBA expcetions
        try:
            transaction = self.get_transaction()
            if transaction is None:
                raise TransactionError('This transaction is terminated.')

            # deleted objects needs special handling
            if isinstance(self.spine_object, Caching) and self.spine_object.is_deleted():
                if isinstance(self.spine_object, Locking):
                    if self.spine_object.has_writelock(transaction):
                        # The transaction has already deleted the object.
                        # The client is really doing something stupid when it tries to
                        # access an object it has already deleted. 20050705 erikgors.
                        raise ObjectDeletedError
                    elif not self.spine_object.is_writelocked():
                        # This object has been deleted _and_ committed.
                        # The transaction might have gotten a reference
                        # from a search, and is now trying to access it.
                        raise ObjectDeletedError
                    else:
                        # We do nothing. The object is marked for deletion
                        # but has not yet been committed, so it might yet be undeleted.
                        # The transaction will get an AlreadyLockedError when it tries
                        # to lock_for_reading/lock_for_writing later on.
                        pass
                elif isinstance(self.spine_object, DatabaseTransactionClass):
                    raise ObjectDeletedError

            # Check for lost locks (raises an exception if a lost lock is found)
            transaction.check_lost_locks()

            # Authorization
            if not transaction.authorization.check_permission(self.spine_object, method.name):
                raise AccessDeniedError('Your are not authorized to perform the requested operation.')

            # Lock the object if it should be locked
            if isinstance(self.spine_object, Locking):
                if method.write:
                    self.spine_object.lock_for_writing(transaction)
                else:
                    self.spine_object.lock_for_reading(transaction)

            # Add a reference to the object in the transaction making the call.
            transaction.add_ref(self.spine_object)

            # convert from CORBA arguments to python server-side arguments
            args = []
            for value, (name, data_type) in zip(corba_args, method.args):
                arg = convert_from_corba(value, data_type)
                if data_type is str:
                    arg = _string_to_db(arg, transaction.get_encoding())
                args.append(arg)

            vargs = {}
            for name, value in corba_vargs:
                data_type = args_table[name]
                varg = convert_from_corba(value, data_type)
                if data_type is str:
                    varg = _string_to_db(varg, transaction.get_encoding())
                vargs[name] = varg

            # Run the real method
            value = getattr(self.spine_object, method.name)(*args, **vargs)

            if method.write:
                self.spine_object.save()

            return convert_to_corba(value, transaction, method.data_type)

        except Communication.CORBA.OBJECT_NOT_EXIST, e:
            raise e

        except Exception, e:
            # SpineIDL is imported here because it doesn't exist during loading
            # of Corba.py 
            import SpineIDL

            if getattr(e, '__class__', e) not in method.exceptions:
                # Temporary raise of unknown exceptions to the client Remember
                # to remove the message given, and remove in Builder.py before
                # production.
                traceback.print_exc()
                name = getattr(e, '__class__', str(e))
                exception_string = "Unknown error '%s':\n%s\n%s" % (
                                    name, hasattr(e, 'args') and str(e.args) or '', 
                                    ''.join(apply(
                                        traceback.format_exception, 
                                        sys.exc_info())))
                raise SpineIDL.Errors.ServerProgrammingError(exception_string)

            if len(e.args) > 0:
                explanation = ', '.join(['%s' % i for i in e.args])
            else:
                explanation = ""
            
            exception = getattr(SpineIDL.Errors, e.__class__.__name__)
            exception = exception(explanation)
            raise exception

    return corba_method

def _get_idl_type_name(arg_t):
    """Returns the IDL name of the given data type."""
    if arg_t == str:
        data_type = 'string'
    elif arg_t == int:
        data_type = 'long'
    elif arg_t == None:
        data_type = 'void'
    elif arg_t == bool:
        data_type = 'boolean'
    elif arg_t == float:
        data_type = 'float'
    elif isinstance(arg_t, Struct):
        cls = arg_t.data_type
        data_type = cls.__name__ + 'Struct'
    elif arg_t == Any:
        data_type = 'any'
    else:
        data_type = 'Spine' + arg_t.__name__
    return data_type

def _docstring_to_idl(comment, tabs=0):
    """
    Converts a Python docstring to a Doxygen-style IDL comment.
    """
    tabs = '\t' * tabs
    comment = _trim_docstring(comment).replace('\n', '\n%s* ' % tabs)
    txt = '%s/**\n' % tabs
    txt += '%s* %s\n' % (tabs, comment)
    txt += '%s*/\n' % tabs
    return txt

def _create_idl_getattr_comment(attr, data_type, tabs=0):
    """
    Creates a comment for the get method for the given attribute for insertion
    in the generated IDL code.
    """
    tabs = '\t' * tabs
    txt = '%s/**\n%s* Get %s.\n%s* \\return A %s object.\n' % (tabs, 
            tabs, attr.name, tabs, data_type)
    for i in attr.exceptions:
        txt += '%s* \\exception SpineIDL::Errors::%s\n' % (tabs, i.__name__)
    txt += '%s*/\n' % tabs
    return txt

def _create_idl_setattr_comment(attr, tabs=0):
    """
    Creates a comment for the set method for the given attribute for insertion
    in the generated IDL code.
    """
    tabs = '\t' * tabs
    txt = '%s/**\n%s* Set %s.\n' % (tabs, tabs, attr.name)
    data_type = _get_idl_type_name(attr.data_type)
    txt += '%s* \\param new_%s The %s to set.\n' % (tabs, attr.name, data_type)
    for i in attr.exceptions:
        txt += '%s* \\exception SpineIDL::Errors::%s\n' % (tabs, i.__name__)
    txt += '%s*/\n' % tabs
    return txt

def _create_idl_method_comment(method, rtn_type, tabs=0):
    """
    Returns a string with a comment for insertion in the generated IDL code.

    The comment has the following syntax:
    /**
    * Auto-generated method comment.
    * \\param argument A [list of] <type> object[s]
    * \\return A <rtn_type> object (if non-void)
    * \\exception <exception>
    */

    If you need the comment to be indented, give the number of tabs
    with 'tabs'.
    """
    if method.doc:
        txt = _docstring_to_idl(method.doc, tabs=tabs)[:-1]
        txt = txt[txt.rfind('\n'):]
        tabs = '\t' * tabs
    else:
        tabs = '\t' * tabs
        txt = '%s/**\n' % tabs
        txt += '%s* Auto-generated method comment.\n' % (tabs)
        for name, arg_type in method.args:
            if type(arg_type) in (list, tuple):
                arg_t, = arg_type
            else:
                arg_t = arg_type
            data_type = _get_idl_type_name(arg_t)

            if type(arg_type) in (list, tuple):
                txt += '%s* \\param %s A list of %s objects.\n' % (tabs, name, data_type)
            else:
                txt += '%s* \\param %s A %s object.\n' % (tabs, name, data_type)

        if rtn_type != 'void':
            txt += '%s* \\return A %s object.\n' % (tabs, rtn_type)
        for i in method.exceptions:
            txt += '%s* \\exception SpineIDL::Errors::%s\n' % (tabs, i.__name__)
        txt += '%s*/\n' % tabs
    return txt

def _trim_docstring(docstring):
    """
    Trims indentation from docstrings.

    This method is copied from PEP 257 regarding docstrings. It was
    placed in public domain by David Goodger & Guido van Rossum, and
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
    """
    Create IDL definition for the class 'cls'.
    
    Creates IDL interface for the class from attributes in cls.slots
    and methods in cls.method_slots.

    If you wish the IDL to be commented, use docs=True. This will copy
    the docstring into the IDL interface for this class.
    """
    def get_exceptions(exceptions, module=""):
        """
        Return the IDL string containing the definitions for all exceptions
        in 'exceptions'.
        """
        if not exceptions:
            return ''
        else:
            if module:
                module += '::'
            # FIXME: sets.Set(exceptions) er nødvendig for å unngå duplikater
            spam = ['%s%s' % (module, i.__name__) for i in sets.Set(exceptions)]
            return '\n\t\traises(%s)' % ', '.join(spam)

    def get_type(data_type):
        """Return a string representing the IDL version of data_type."""
        if type(data_type) == list:
            elem_name = get_type(data_type[0])
            name = elem_name + 'Seq'
            add_header('typedef sequence<%s> %s;' % (elem_name, name))
        elif data_type == str:
            name = 'string'
        elif data_type == int:
            name = 'long'
        elif data_type == None:
            name = 'void'
        elif data_type == bool:
            name = 'boolean'
        elif data_type == float:
            name = 'float'
        elif isinstance(data_type, Struct):
            cls = data_type.data_type
            name = cls.__name__ + 'Struct'
            header = 'struct %s {\n' % name

            for attr in cls.slots:
                data_type = attr.data_type
                if data_type == Date:
                    data_type = str
                header += '\t%s %s;\n' % (get_type(data_type), attr.name)
                if attr.optional:
                    header += '\tboolean %s_exists;\n' % attr.name

            header += '};'

            add_header(header)
        elif data_type == Any:
            name = 'any'
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
    
    # Convert the class comment to IDL
    if docs and cls.__doc__:
        txt += _docstring_to_idl(cls.__doc__)
    
    txt += 'interface Spine%s' % cls.__name__

    # Inheritance
    parent_slots = sets.Set()
    parent_slots_names = sets.Set()
    if cls.builder_parents:
        spam = sets.Set(cls.builder_parents)
        txt += ': ' + ', '.join(['Spine' + i.__name__ for i in spam])
        for i in cls.builder_parents:
            parent_slots.update(i.slots)
            parent_slots.update(i.method_slots)

            for attr in i.slots:
                parent_slots_names.add(attr.get_name_get())
                if attr.write:
                    parent_slots_names.add(attr.get_name_set())
            for method in i.method_slots:
                parent_slots_names.add(method.name)

    txt += ' {\n'

    def checkName(name, names=sets.Set()):
        if name in names or name in parent_slots_names:
            msg = 'Class %s has duplicate definitions of "%s"' % (cls.__name__, name)
            raise ServerProgrammingError(msg)
        names.add(name)

    # Attributes
    if docs and cls.slots:
        txt += '\t// Get and set methods for attributes\n'
    for attr in cls.slots:
        if attr in parent_slots:
            continue
        checkName(attr.get_name_get())
        if attr.write:
            checkName(attr.get_name_set())
        if not hasattr(cls, attr.get_name_get()) or (attr.write and not hasattr(cls, 
                attr.get_name_set())):
            msg = 'Class %s has no method %s, check declaration of %s.slots.'
            raise ServerProgrammingError(msg % (cls.__name__, method.name, cls.__name__))

        exceptions_headers.extend(attr.exceptions)
        excp = get_exceptions(attr.exceptions, error_module)

        data_type = get_type(attr.data_type)

        # TODO: Create improved attribute documentation
        if docs:
            txt += _create_idl_getattr_comment(attr, data_type, 1)

        txt += '\t%s get_%s()%s;\n' % (data_type, attr.name, excp)
        txt += '\n'

        if attr.write:
            args = ((attr.name, attr.data_type),)
            if docs:
                txt += _create_idl_setattr_comment(attr, 1)
            txt += '\tvoid set_%s(in %s new_%s)%s;\n' % (attr.name, data_type, attr.name, excp)
            txt += '\n'

    # Methods
    if docs and cls.slots and cls.method_slots:
        txt += '\t// Other methods\n'
    for method in cls.method_slots:
        if method in parent_slots:
            continue

        checkName(method.name)

        # If the class does not have the method, then method_slots contains an
        # invalid method declaration
        if not hasattr(cls, method.name):
            msg = 'Class %s has no method %s, check declaration of %s.method_slots.'
            raise ServerProgrammingError(msg % (cls.__name__, method.name, cls.__name__))

        args = []
        for name, data_type in method.args:
            #args.append('in %s in_%s' % (get_type(data_type), name))
            args.append('in %s %s' % (get_type(data_type), name))

        data_type = get_type(method.data_type)
        
        exceptions_headers.extend(method.exceptions)
        excp = get_exceptions(method.exceptions, error_module)

        if method.doc is None and hasattr(cls, method.name):
            method.doc = getattr(cls, method.name).__doc__
        #doc = _trim_docstring(method.doc or '')
        
        if docs:
            txt += _create_idl_method_comment(method, data_type, 1)

        txt += '\t%s %s(%s)%s;\n' % (data_type, method.name, ', '.join(args), excp)
        txt += '\n'

    txt += '};\n'
    
    return headers, exceptions_headers, txt

def _create_idl_exceptions(exceptions, docs=False):
    """Creates an Errors module holding the exceptions."""
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
    """
    Create IDL for classes in 'classes'.

    Creates the IDL source for the classes in 'classes' under the
    module name 'module_name'.

    If you wish the IDL to be commented, use docs=True. This will copy
    the docstring into the IDL.
    """
    # Prepare headers, exceptions and lines for all classes.
    headers = []        # contains headers for all classes.
    exceptions = []     # contains exceptions for the module.
    lines = []          # contains interface definitions for all classes.
    
    for cls in classes:
        values = _create_idl_interface(cls, 'Errors', docs)
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
    """
    Base class for all CORBA classes.

    All classes we are gonna send to clients through CORBA will inherit
    from this class.
    """
    
    def __init__(self, spine_object, transaction):
        self.spine_object = spine_object
        self.get_transaction = weakref.ref(transaction)


def register_spine_class(cls, idl_cls, idl_struct):
    """
    Create CORBA class for the class 'cls'.

    Registers structs and classes in corba_structs and class_cache.
    Creates a corbaclass for the class, and builds corbamethods in it.
    """
    name = cls.__name__
    corba_class_name = 'Spine' + name

    corba_structs[cls] = idl_struct

    exec 'class %s(CorbaClass, idl_cls):\n\tpass\ncorba_class = %s' % (
        corba_class_name, corba_class_name)

    corba_class.spine_class = cls

    names = sets.Set()

    for attr in cls.slots:
        get_name = attr.get_name_get()
        get = Method(get_name, attr.data_type, exceptions=attr.exceptions)

        setattr(corba_class, get_name, _create_corba_method(get))

        if attr.write:
            set_name = attr.get_name_set()
            set = Method(set_name, None, [(attr.name, attr.data_type)],
                         exceptions=attr.exceptions, write=True)

            setattr(corba_class, set_name, _create_corba_method(set))

    classes = (cls, ) + cls.builder_parents
    for i in classes:
        for method in i.method_slots:
            if not hasattr(corba_class, method.name):
                setattr(corba_class, method.name, _create_corba_method(method))

    class_cache[cls] = corba_class

# arch-tag: d64745f8-6ea2-469e-b821-b0f448ab7e4a
