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

import sets
import types

import SpineExceptions

__all__ = ['Attribute', 'Method', 'Builder']

default_exceptions = (
    SpineExceptions.TransactionError,
    SpineExceptions.AccessDeniedError,
    SpineExceptions.ObjectDeletedError,
    SpineExceptions.NotFoundError,
    SpineExceptions.ServerProgrammingError
)

not_set = object()

class Attribute(object):
    """Representation of an attribute in Spine.

    Attributes are used to collect metainfo about attributes which Spine
    should provide to clients and internally for Spine-classes.

    After Spine-classes are built, Spine will generate get/load-methods
    for attributes of this class, or subclass, which are listed, in a
    class or subclass of Builder, in primary and slots. Attributes which
    are writeable, will also get set/save-methods.
    """
    
    def __init__(self, name, data_type, exceptions=None, write=False, optional=False):
        """Initiate the attribute.

        name        - the name of the attribute in a string.
        data_type   - should be a class or a type, like Entity, list, str, None.
        exceptions  - list with all exceptions accessing this attribute might raise.
        write       - should be True if the clients are allowed to change this attribute.
        optional    - for attributes which is not mandatory to be set.

        optional attributes have exists-comparisation in searchobjects.
        """
        assert type(data_type) != str
        assert write in (True, False)
        assert optional in (True, False)

        self.name = name
        self.data_type = data_type
        self.exceptions = default_exceptions + tuple(exceptions or ())
        if optional:
            self.exceptions += (SpineExceptions.NotFoundError, SpineExceptions.TooManyMatchesError)
        self.write = write
        self.optional = optional

        self.var_get = 'get_' + self.name
        self.var_set = 'set_' + self.name
        self.var_load = 'load_' + self.name
        self.var_save = 'save_' + self.name
        self.var_private = '_' + self.name

    def __repr__(self):
        return '%s(%s, %s)' % (self.__class__.__name__, `self.name`, `self.data_type`)

class Method(object):
    """Representation of a method in Spine.

    Methods are used to collect metainfo about methods which should be
    provided to clients. Information like arguments and return-type is
    used when generating idl for use in corba.

    The methods will be wrapped to allow for authentication and access
    control.

    If the method is "write" and the object is a subclass of Locking, the
    object will be locked for writing before the method is called.
    """
    
    def __init__(self, name, data_type, args=None, exceptions=None, write=False):
        """Initiate the method.

        name        - the name of the method as a string.
        data_type   - the return type, should be a class or type: str, list, Entity.
        args        - a list with lists of arguments, like (("name", str), ("blipp", list")).
        exceptions  - list with all exceptions accessing this attribute might raise.
        write       - should be True for methods which change and object and/or require write locks.
        """
        self.name = name
        assert type(data_type) != str
        assert write in (True, False)

        self.data_type = data_type
        self.args = args or ()
        self.exceptions = default_exceptions + tuple(exceptions or ())
        self.write = write
        self.doc = None
        try: raise RuntimeError
        except RuntimeError:
            import sys
            e, b, t = sys.exc_info()
            caller_dict = t.tb_frame.f_back.f_globals
            e_file = caller_dict['__file__']
            e_line = t.tb_frame.f_back.f_lineno
            print "DeprecationWarning:SpineLib:Method, %s in %s:%s" % (self.name, e_file, e_line)

    def upgrade(self, method_func):
        assert not hasattr(method_func, "im_func")
        method_func.signature = self.data_type
        method_func.signature_name = self.name
        method_func.signature_named_args = self.args
        method_func.signature_exceptions = self.exceptions
        if self.write:
            method_func.signature_write = self.write
        return method_func

    def __repr__(self):
        return '%s(%s, %s)' % (self.__class__.__name__, `self.name`, `self.data_type`)

def get_method_signature(func):
    """ Get the signature from method in Spine.

    Allowed fields for the signature:

    signature
        - the return type, should be a class or type: str, list, Entity.
    signature_name
        - overrides func_name
    signature_args
        - a list with data_types for arguments used
    signature_named_args
        - a list with (arg_name, data_type), for use when introspection doesn't cut it
    signature_exceptions
        - list with all exceptions accessing this attribute might raise.
    signature_write
    write
        - set to True for methods which change and object and/or require write locks.

    returns name, signature, write, args, exceptions

    Example:

    def test(self, a):
        return 1337 + a

    test.signature = int
    test.signature_args = [int]
    """
    
    signature = func.signature # need to know the return data type
    assert func.func_defaults is None # default values are useless with corba

    if type(func) == types.MethodType:
        func = func.im_func

    named_args = getattr(func, 'signature_named_args', ())

    if named_args:
        args = named_args
    else:
        offset = 0

        if func.func_code.co_varnames[0] == 'self':
            offset = 1

        signature_args = getattr(func, 'signature_args', ())
        count = func.func_code.co_argcount # first argument is skipped (self)

        assert len(signature_args) == count - offset # data type needs to be defined for all args
    
        args = zip(func.func_code.co_varnames[offset:count], signature_args)

    name = getattr(func, 'signature_name', '') or func.func_name
    write = hasattr(func, 'signature_write')
    exceptions = default_exceptions
    exceptions += tuple(getattr(func, 'signature_exceptions', ()))

    return name, signature, write, args, exceptions

def create_lazy_get_method(attr):
    """Returns a method which will load the attribute if not already loaded."""
    def lazy_get(self):
        value = getattr(self, attr.var_private, not_set)
        if value is not_set:
            loadmethod = getattr(self, attr.var_load, not_set)
            if loadmethod is not not_set:
                loadmethod()
            value = getattr(self, attr.var_private, None)
        return value
    return lazy_get

def create_set_method(attr):
    """Returns a method which will save the value, if its updated."""
    def set(self, value):
        # make sure the variable has been loaded
        orig = getattr(self, attr.var_get)

        if orig is not value: # we only set a new value if it is different
            # set the variable
            setattr(self,attr.var_private, value)
            # mark it as updated
            self.updated.add(attr)
    return set

class Builder(object):
    """Core class for Spine for providing building functionality.
    
    Provides functionality for building methods for attributes, and for
    registering methods and attributes to the class.

    Attributes which subclasses should implement:
    'primary' should contain attributes which are unique for objects.
    'slots' should contain the rest of the attributes for the class.
    """
    
    primary = ()
    slots = ()
    _ignore_Builder = True

    def __init__(self, *args, **vargs):
        map = self.map_attributes(*args, **vargs)
        
        # set all variables give in args and vargs
        for attr, value in map.items():
            if not hasattr(self, attr.var_private):
                setattr(self, attr.var_private, value)

        # used to track changes
        if not hasattr(self, 'updated'):
            self.updated = sets.Set()

    def save(self):
        """Save all changed attributes."""
        saved = sets.Set()
        for attr in list(self.updated):
            save_method = getattr(self, attr.var_save, None)
            if save_method not in saved and save_method is not None:
                save_method()
                saved.add(save_method)
        assert not self.updated

    def reset(self, write_only=True):
        """Reset all changed attributes.
        
        Use write_only=False to reset attributes who are not writeable.
        Usefull for methods which alters the values the attributes represent
        without going through the usual Spine-API-methods.
        """
        loaded = sets.Set()
        for attr in self.slots:
            if attr not in self.primary:
                if write_only and not attr.write:
                    continue
                if hasattr(self, attr.var_private):
                    delattr(self, attr.var_private)
        self.updated.clear()

    def create_primary_key(cls, *args, **vargs):
        """Create primary key from args and vargs.

        Used by the caching facility to identify a unique object.
        """

        # this should be kind of optimized...

        key = []
        try:
            if not vargs:
                for i in xrange(len(cls.primary)):
                    key.append(args[i])
            else:
                args = iter(args)
                for i in cls.primary:
                    try:
                        key.append(vargs[i.name])
                    except KeyError:
                        key.append(args.next())
        except IndexError, e:
            raise TypeError, 'Missing primary key: %s' % (cls.primary, )

        return tuple(key)

    create_primary_key = classmethod(create_primary_key)
 
    def register_attribute(cls, attr, load=None, save=None, get=None, set=None):
        """Registers an attribute.

        load - loads the value for this attribute
        save - saves a new attribute
        get  - returns the value
        set  - sets the value. Validation can be done here.

        methods not set (to None or a real method) will be generated.

        load/save/get/set must take self as first argument.

        If get and set is None, the default behavior is for set and get to use
        self._`attribute.name`. load will then be run automatically by get if the
        attribute has not yet been loaded.

        If attribute is not write, save will not be used.
        """

        assert attr not in cls.slots
        if not attr.write: # set methods doesnt make sense when attribute is not writeable
            assert set is None

        cls.slots += (attr, )
        if get is not None:
            setattr(cls, attr.var_get, get)
        if set is not None:
            setattr(cls, attr.var_set, set)
        if load is not None:
            setattr(cls, attr.var_load, load)
        if save is not None:
            setattr(cls, attr.var_save, save)

    register_attribute = classmethod(register_attribute)

    def get_attribute(cls, name):
        """Get the attribute in slots with name 'name'."""
        # FIXME: get_slot bedre navn? 20060309 erikgors
        for attr in cls.slots:
            if attr.name == name:
                return attr
        raise KeyError('Attribute %s not found in %s' % (name, cls))

    get_attribute = classmethod(get_attribute)

    def map_attributes(cls, *args, **vargs):
        """Returns a dict with attribute:value."""

        map = {}
        for attr, value in zip(cls.slots, args):
            map[attr] = value

        if vargs:
            slotMap = dict([(i.name, i) for i in cls.slots])

            for key, value in vargs.items():
                attr = slotMap.get(key)
                if attr is None:
                    continue
                map[attr] = value

        return map

    map_attributes = classmethod(map_attributes)

    def register_methods(cls, methods):
        for i in methods:
            name, signature, write, args, exceptions = get_method_signature(i)
            setattr(cls, name, i)
    register_methods = classmethod(register_methods)

    def register_method(cls, method, method_func, overwrite=False):
        """Deprecated.  Convert the method and use register_methods
        instead."""
        method.upgrade(method_func)
        cls.register_methods([method_func])
    register_method = classmethod(register_method)

    def build_methods(cls):
        """Create get/set methods for all slots."""
        assert type(cls.primary) == tuple
        assert type(cls.slots) == tuple
        
        if cls.primary != cls.slots[:len(cls.primary)]:
            cls.slots = cls.primary + cls.slots

        for attr in cls.slots:
            if not hasattr(cls, attr.var_get):
                setattr(cls, attr.var_get, create_lazy_get_method(attr))

            get = getattr(cls, attr.var_get)
            if type(get) == types.MethodType:
                get = get.im_func
            get.signature = attr.data_type
            get.signature_name = attr.var_get
             
            if attr.write:
                if not hasattr(cls, attr.var_set):
                    setattr(cls, attr.var_set, create_set_method(attr))

                set = getattr(cls, attr.var_set)
                if type(set) == types.MethodType:
                    set = set.im_func
                    set.signature = None
                    set.signature_name = attr.var_set
                    set.signature_write = True
                    set.signature_args = [attr.data_type]
            else:
                assert not hasattr(cls, attr.var_set)


    build_methods = classmethod(build_methods)

    def builder_ignore(cls):
        return hasattr(cls, '_ignore_' + cls.__name__) and getattr(cls, '_ignore_' + cls.__name__)

    builder_ignore = classmethod(builder_ignore)

def get_builder_classes(cls=Builder):
    for i in cls.__subclasses__():
        yield i
        for j in get_builder_classes(i):
            yield j

def build_everything():
    for i in get_builder_classes():
        i.build_methods()

def get_builder_methods(cls):
    for i in dir(cls):
        if i[0] != '_':
            i = getattr(cls, i)
            if type(i) == types.MethodType:
                i = i.im_func
            if hasattr(i, 'signature'):
                yield i


# arch-tag: fa55df79-985c-4fab-90f8-d1fefd85fdbb
