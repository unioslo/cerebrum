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

import time

from Cerebrum.extlib import sets
from Cerebrum.spine.server.Cerebrum_core import Errors

__all__ = ['Attribute', 'Method', 'Builder']


class Attribute(object):
    def __init__(self, name, data_type, exceptions=(), write=False):
        self.name = name
        assert type(data_type) != str
        assert type(exceptions) in (list, tuple)
        assert write in (True, False)

        self.data_type = data_type
        self.exceptions = exceptions
        self.write = write

    def get_name_get(self):
        return 'get_' + self.name

    def get_name_set(self):
        return 'set_' + self.name

    def get_name_private(self):
        return '_' + self.name

    def get_name_load(self):
        return 'load_' + self.name

    def get_name_save(self):
        return 'save_' + self.name

    def __repr__(self):
        return '%s(%s, %s)' % (self.__class__.__name__, `self.name`, `self.data_type`)

class Method(object):
    def __init__(self, name, data_type, args=(), exceptions=(), write=False):
        self.name = name
        assert type(data_type) != str
        assert type(exceptions) in (list, tuple)
        assert write in (True, False)

        self.data_type = data_type
        self.args = args
        self.exceptions = exceptions
        self.write = write

    def __repr__(self):
        return '%s(%s, %s)' % (self.__class__.__name__, `self.name`, `self.data_type`)

def create_lazy_get_method(attr):
    def lazy_get(self):
        lazy = object() # a unique object.
        value = getattr(self, attr.get_name_private(), lazy)
        if value is lazy:
            loadmethod = getattr(self, attr.get_name_load(), None)
            if loadmethod is None:
                raise NotImplementedError('load for this attribute is not implemented')
            loadmethod()
            value = getattr(self, attr.get_name_private(), lazy)
            assert value is not lazy # fails if loadmethod didnt load a new value
        return value
    return lazy_get

def create_set_method(attr):
    def set(self, value):
        # make sure the variable has been loaded
        orig = getattr(self, attr.get_name_get())

        if orig is not value: # we only set a new value if it is different
            # set the variable
            setattr(self,attr.get_name_private(), value)
            # mark it as updated
            self.updated.add(attr)
    return set

def create_readonly_set_method(attr):
    def readonly_set(self, *args, **vargs):
        raise Errors.ReadOnlyAttributeError('attribute %s is read only' % attr.name)
    return readonly_set

class Builder(object):
    primary = []
    slots = []
    method_slots = []

    builder_parents = ()
    builder_children = ()

    def __init__(self, *args, **vargs):
        map = self.map_args(*args, **vargs)
        
        # set all variables give in args and vargs
        for attr, value in map.items():
            var = attr.get_name_private()
            if not hasattr(self, var):
                setattr(self, var, value)

        # used to track changes
        if not hasattr(self, 'updated'):
            self.updated = sets.Set()

    def map_args(cls, *args, **vargs):
        slotMap = dict([(i.name, i) for i in cls.slots])

        map = dict(zip(cls.slots, args))

        for key, value in vargs.items():
            attr = slotMap.get(key)
            if attr is None:
                continue
            map[attr] = value

        return map

    map_args = classmethod(map_args)

    def save(self):
        """ Save all changed attributes """

        saved = sets.Set()
        for attr in self.updated:
            save_method = getattr(self, 'save_' + attr.name)
            if save_method not in saved:
                save_method()
                saved.add(save_method)
        self.updated.clear()

    def reset(self):
        """ Reload all changed attributes """

        loaded = sets.Set()
        for attr in self.slots:
            if attr not in self.primary:
                load_method = getattr(self, 'load_' + attr.name)
                if load_method not in loaded:
                    load_method()
                    loaded.add(load_method)
        self.updated.clear()

    # class methods
    
    def create_primary_key(cls, *args, **vargs):
        """ Create primary key from args and vargs

        Used by the caching facility to identify a unique object
        """

        names = [i.name for i in cls.primary]
        for var, value in zip(names, args):
            vargs[var] = value

        key = []
        for i in names:
            key.append(vargs[i])
        return tuple(key)

    create_primary_key = classmethod(create_primary_key)
 
    def register_attribute(cls, attribute, load=None, save=None, get=None, set=None, overwrite=False, override=False, register=True):
        """ Registers an attribute

        attribute contains the name and data_type as it will be in the API
        load - loads the value for this attribute
        save - saves a new attribute
        get  - returns the value
        set  - sets the value. Validation can be done here.

        load/save/get/set must take self as first argument.

        overwrite - decides whether to overwrite existing definitions

        If the attribute does not exist, it will be added to the class
        If overwrite=True load/save/get/set will be overwritten if they allready exists.

        If get and set is None, the default behavior is for set and get to use
        self._`attribute.name`. load will then be run automatically by get if the
        attribute has not yet been loaded.

        If attribute is not write, save will not be used.
        """

        var_private = attribute.get_name_private()
        var_get = attribute.get_name_get()
        var_set = attribute.get_name_set()
        var_load = attribute.get_name_load()
        var_save = attribute.get_name_save()

        if get is None:
            get = create_lazy_get_method(attribute)

        if set is None:
            if attribute.write:
                set = create_set_method(attribute)
            else:
                set = create_readonly_set_method(attribute)

        def quick_register(var, method):
            if method is not None: # no use setting a to None
                if hasattr(cls, var) and not overwrite:
                    raise AttributeError('%s already exists in %s' % (var, cls.__name__))
                setattr(cls, var, method)

        quick_register(var_load, load)
        quick_register(var_save, save)
        quick_register(var_get, get)
        quick_register(var_set, set)

        if register:
            cls.slots.append(attribute)

    register_attribute = classmethod(register_attribute)

    def register_method(cls, method, method_func, overwrite=False):
        """ Registers a method
        """
        if hasattr(cls, method.name) and not overwrite:
            raise AttributeError('%s already exists in %s' % (method.name, cls.__name__))
        setattr(cls, method.name, method_func)
        cls.method_slots.append(method)

    register_method = classmethod(register_method)

    def build_methods(cls):
        if cls.primary != cls.slots[:len(cls.primary)]:
            cls.slots = cls.primary + cls.slots
        for attr in cls.slots:
            get = getattr(cls, attr.get_name_get(), None)
            set = getattr(cls, attr.get_name_set(), None)
            cls.register_attribute(attr, get=get, set=set, overwrite=True, register=False)

    build_methods = classmethod(build_methods)

# arch-tag: fa55df79-985c-4fab-90f8-d1fefd85fdbb
