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
import weakref

import cereconf
import Communication


from Cerebrum.extlib import sets
from Cerebrum.spine.SpineLib import Builder
from Cerebrum.spine.SpineLib.Date import Date
from Cerebrum.spine.SpineLib.DumpClass import Struct, DumpClass
from Cerebrum.spine.SpineLib.Locking import Locking
from Cerebrum.spine.SpineLib.Caching import Caching
from Cerebrum.spine.SpineLib.DatabaseClass import DatabaseTransactionClass
from Cerebrum.spine.SpineLib.SearchClass import SearchClass
from Cerebrum.spine.SpineLib.SpineExceptions import AccessDeniedError, ServerProgrammingError, TransactionError, ObjectDeletedError

__all__ = ['convert_to_corba', 'convert_from_corba',
           'create_idl_source', 'register_spine_class','drop_associated_objects']

from Cerebrum.Utils import Factory
logger = Factory.get_logger()

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
            logger.exception('Unable to remove reference when dropping from object cache!')
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
            msg='Unable to convert object %s to CORBA; object is not a list.' % (obj.__class__.__name__)
            logger.exception(msg)
            raise ServerProgrammingError(msg)

    elif data_type in class_cache:
        # corba casting
        if obj.__class__ in class_cache:
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
    else:
        raise ServerProgrammingError('Cannot convert to CORBA type; unknown data type.', data_type)

def convert_from_corba(tr, obj, data_type):
    """Convert a CORBA object to a python object."""
    if data_type is str:
        return _string_to_db(obj, tr.get_encoding())
    elif data_type in corba_types:
        return obj
    elif type(data_type) == list:
        return [convert_from_corba(tr, i, data_type[0]) for i in obj]
    elif obj is None:
        return None
    elif data_type in class_cache:
        corba_class = class_cache[data_type]
        com = Communication.get_communication()
        return com.reference_to_servant(obj).spine_object
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

# FIXME: coding should be set in db... 20060310 erikgors.

def _string_from_db(str, encoding):
    """
    Converts a string from the database string encoding to the clients
    string encoding.
    """
    if encoding == getattr(cereconf, 'SPINE_DATABASE_ENCODING', 'iso-8859-1'):
        return str
    return str.decode(getattr(cereconf, 'SPINE_DATABASE_ENCODING', 'iso-8859-1')).encode(encoding)

def _string_to_db(str, encoding):
    """
    Converts a string from the clients string encoding to the database string
    encoding.
    """
    if encoding == getattr(cereconf, 'SPINE_DATABASE_ENCODING', 'iso-8859-1'):
        return str
    return str.decode(encoding).encode(getattr(cereconf, 'SPINE_DATABASE_ENCODING', 'iso-8859-1'))

def _create_corba_method(method, method_name, data_type, write, method_args, exceptions, auth_attr=None):
    """
    Creates a wrapper for the given method. 

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
    if auth_attr != None:
        assert auth_attr < len(method_args)
        assert hasattr(method_args[auth_attr][1], "auth_str")
    
    def corba_method(self, *corba_args):
        assert len(corba_args) == len(method_args)

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

            # Convert arguments
            args = [convert_from_corba(transaction, obj, i[1]) for obj, i in zip(corba_args, method_args)]

            # Can the logged in user run this method?
            attr_str=None
            if auth_attr != None:
                attr_str = args[auth_attr].auth_str()

            if not transaction.authorization.has_permission(method_name, self.spine_object, attr_str):
                raise AccessDeniedError('You are not authorized to perform the requested operation: %s.%s' % (self.spine_object.__class__.__name__, method_name))

            # Lock the object if it should be locked
            if isinstance(self.spine_object, Locking):
                if write:
                    self.spine_object.lock_for_writing(transaction)
                else:
                    self.spine_object.lock_for_reading(transaction)

            # Add a reference to the object in the transaction making the call.
            transaction.add_ref(self.spine_object)
            # Run the real method
            value = method(self.spine_object, *args)
            
            if write:
                self.spine_object.save()

            return convert_to_corba(value, transaction, data_type)

        except Communication.CORBA.OBJECT_NOT_EXIST, e:
            raise e

        except Exception, e:
            # SpineIDL is imported here because it doesn't exist during loading
            # of Corba.py 
            import SpineIDL
            
            if len(e.args) > 0:
                explanation = ', '.join(['%s' % i for i in e.args])
            else:
                explanation = ""

            if getattr(e, '__class__', e) not in exceptions:
                # This is for unhandeled exceptions in spine...
                # This is by definition a bug in spine, but let's
                # play nice and tell the user what's going on.
                
                # Log a traceback for debugging
                logger.exception("")
                
                # And make a nice descriptice error for the user
                explanation = e.__class__.__name__ + ": " + explanation
                exception = SpineIDL.Errors.ServerError
            else:
                exception = getattr(SpineIDL.Errors, e.__class__.__name__)

            exception = exception(explanation)

            raise exception

    return corba_method

def _docstring_to_idl(method_name, comment, tabs=0):
    """
    Converts a Python docstring to a Doxygen-style IDL comment. In addition
    to saving the string as a pseudo-docstring in IDL.
    """
    txt = _docstring_to_idl_comment(method_name, comment, tabs)
    txt += _docstring_to_idl_docstring(method_name, comment, tabs)
    return txt

def _docstring_to_idl_comment(method_name, comment, tabs=0):
    """
    Converts a Python docstring to a Doxygen-style IDL comment.
    """
    tabs = '\t' * tabs
    comment = _trim_docstring(comment).replace('\n', '\n%s* ' % tabs)
    txt = '%s/**\n' % tabs
    txt += '%s* %s\n' % (tabs, comment)
    txt += '%s*/\n' % tabs
    return txt

def _docstring_to_idl_docstring(method_name, comment, tabs=0):
    """
    Converts a Python docstring to a pseudo-docstring in IDL.
    """
    tabs = '\t' * tabs
    comment = _trim_docstring(comment).replace('\\', '\\\\').replace('"', '\"')
    txt = '%sconst string %s__doc__ = "%s";\n' % (tabs, method_name, comment)
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
    and methods found by calling Builder.get_builder_methods.

    If you wish the IDL to be commented, use docs=True. This will copy
    the docstring into the IDL interface for this class.
    """
    def create_method_comment(name, args, rtn_type, exceptions, doc=None, tabs=0):
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
        auto_doc = ['Auto-generated method comment.']
        for arg_name, arg_t in args:
            data_type = get_type(arg_t)
            if data_type.endswith('Seq'):
                auto_doc.append('\\param %s A list of %s objects.' % (arg_name, data_type))
            else:
                auto_doc.append('\\param %s A %s object.' % (arg_name, data_type))

        if rtn_type != 'void':
            auto_doc.append('\\return A %s object.' % (rtn_type))
        for i in exceptions:
            auto_doc.append('\\exception SpineIDL::Errors::%s' % (i.__name__))

        if doc:
            auto_doc.append('Original method comment.')
            auto_doc.append(doc)

        doc = "\n".join(auto_doc)

        return _docstring_to_idl(name, doc, tabs)

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

        if not type(data_type) == type:
            d_type = type(data_type)
        else:
            d_type = data_type

        if d_type == list:
            elem_name = get_type(data_type[0])
            name = elem_name + 'Seq'
            add_header('typedef sequence<%s> %s;' % (elem_name, name))
        elif d_type == str:
            name = 'string'
        elif d_type == int:
            name = 'long'
        elif data_type == None:
            name = 'void'
        elif d_type == bool:
            name = 'boolean'
        elif d_type == float:
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
        else:
            assert data_type.__name__ not in ['str', 'int', 'float', 'bool'], data_type
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
        txt += _docstring_to_idl_comment(cls.__name__, cls.__doc__)
    
    txt += 'interface Spine%s' % cls.__name__

    # Inheritance
    parent_methods = sets.Set()
    parent_slots = sets.Set()

    parents = []

    if issubclass(cls, object):
        for parent in cls.__mro__[1:]:
            assert not hasattr(parent, 'method_slots')
            if not hasattr(parent, 'slots'): # duck typing
                continue
            methods = list(Builder.get_builder_methods(parent))
            if not methods:
                continue
            parent_methods.update(methods)
            parents.append('Spine' + parent.__name__)
    else:
        assert cls.__name__ == 'Session', cls.__name__

    assert not hasattr(cls, 'method_slots') 

    if parents:
        txt += ': ' + ', '.join(parents)

    txt += ' {\n'

    if docs and cls.__doc__:
        txt += _docstring_to_idl_docstring('Spine%s' % cls.__name__, cls.__doc__)
    
    for method in Builder.get_builder_methods(cls):
        if method in parent_methods:
            continue
        name, data_type, write, args, exceptions, auth_attr = Builder.get_method_signature(method)

        data_type = get_type(data_type)

        def getArgs():
            for name, data_type in args:
                yield 'in %s new_%s' % (get_type(data_type), name)
        
        exceptions_headers.extend(exceptions)
        excp = get_exceptions(exceptions, error_module)

        if docs:
            doc = getattr(method, '__doc__', None)
            txt += create_method_comment(name, args, data_type, exceptions, doc=doc)
        txt += '\t%s %s(%s)%s;\n' % (data_type, name, ', '.join(getArgs()), excp)
        
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
        # FIXME: is weakref really a point here? 20060309 erikgors
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

    for method in Builder.get_builder_methods(cls):
        name, data_type, write, args, exceptions, auth_attr = Builder.get_method_signature(method)

        setattr(corba_class, name, _create_corba_method(method, name, data_type, write, args, exceptions, auth_attr))

    class_cache[cls] = corba_class

# arch-tag: d64745f8-6ea2-469e-b821-b0f448ab7e4a
