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

import time

from Cerebrum.extlib import sets
from Cerebrum.gro.Cerebrum_core import Errors

__all__ = ['Attribute', 'Method', 'Builder']


class Attribute(object):
    def __init__(self, name, data_type, exceptions=None, write=False):
        self.type = 'Attribute'
        self.name = name
        self.data_type = data_type
        if exceptions is None:
            exceptions = []
        self.exceptions = exceptions
        self.write = write

        #FIXME: disse _må_ bort
        self.get = None
        self.set = None

    def __repr__(self):
        return '%s(%s, %s)' % (self.__class__.__name__, `self.name`, `self.data_type`)

class Method(object):
    def __init__(self, name, data_type, args=None, exceptions=None, write=False):
        self.type = 'Method'
        self.name = name
        self.data_type = data_type
        if args is None:
            args = []
        self.args = args
        if exceptions is None:
            exceptions = []
        self.exceptions = exceptions
        self.write = write

    def __repr__(self):
        return '%s(%s, %s)' % (self.__class__.__name__, `self.name`, `self.data_type`)

def create_lazy_get_method(var, load):
    assert type(var) == str
    assert type(load) == str

    def lazy_get(self):
        lazy = object()
        value = getattr(self, var, lazy)
        if value is lazy:
            loadmethod = getattr(self, load, None)
            if loadmethod is None:
                raise NotImplementedError('load for this attribute is not implemented')
            loadmethod()
            value = getattr(self, var, lazy)
            assert value is not lazy
        return value
    return lazy_get

def create_set_method(var):
    assert type(var) == str

    def set(self, value):
        # make sure the variable has been loaded
        orig = getattr(self, 'get_' + var)

        if orig is not value: # we only set a new value if it is different
            # set the variable
            setattr(self, '_' + var, value)
            # mark it as updated
            self.updated.add(var)
    return set

def create_readonly_set_method(var):
    def readonly_set(self, *args, **vargs):
        raise Errors.ReadOnlyAttributeError('attribute %s is read only' % var)
    return readonly_set

class Builder(object):
    primary = []
    slots = []
    method_slots = []

    def __init__(self, *args, **vargs):
        if len(args) + len(vargs) > len(self.slots):
            raise TypeError('__init__() takes at most %s argument%s (%s given)' % (len(self.slots) + 1,
                            len(self.slots)>0 and 's' or '', len(args) + len(vargs) + 1))

        cls = self.__class__
        mark = '_%s%s' % (cls.__name__, id(self))
        # check if the object is old
        if hasattr(self, mark):
            return getattr(self, mark)
        
        slotNames = [i.name for i in cls.slots]

        for key in vargs.keys():
            if key not in slotNames:
                raise TypeError("__init__() got an unexpected keyword argument '%s'" % key)

        # set all variables give in args and vargs
        for var, value in zip(slotNames, args) + vargs.items():
            setattr(self, '_' + var, value)

        # used to track changes
        if not hasattr(self, 'updated'):
            self.updated = sets.Set()

        # mark the object as old
        setattr(self, mark, time.time())

    def save(self):
        """ Save all changed attributes """

        saved = sets.Set()
        for var in self.updated:
            save_method = getattr(self, 'save_' + var)
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
        override  - decides whether to raise an exception when a definition of this
                    attribute allready exists

        If the attribute does not exist, it will be added to the class
        If overwrite=True load/save/get/set will be overwritten if they allready exists.
        If override=False and load/save/get/set exists, an exception will be raised.

        If get and set is None, the default behavior is for set and get to use
        self._`attribute.name`. load will then be run automatically by get if the
        attribute has not yet been loaded.

        If attribute is not write, save will not be used.
        """

        var_private = '_' + attribute.name
        var_get = 'get_' + attribute.name
        var_set = 'set_' + attribute.name
        var_load = 'load_' + attribute.name
        var_save = 'save_' + attribute.name

        if get is None:
            get = create_lazy_get_method(var_private, var_load)

        if set is None:
            if attribute.write:
                set = create_set_method(attribute.name)
            else:
                set = create_readonly_set_method(attribute.name)

        def quick_register(var, method):
            if hasattr(cls, var) and not overwrite:
                if not override:
                    raise AttributeError('%s already exists in %s' % (var, cls.__name__))
            elif method is not None: # no use setting a to None
                setattr(cls, var, method)

        quick_register(var_load, load)
        quick_register(var_save, save)
        quick_register(var_get, get)
        quick_register(var_set, set)

        # save get/set to attribute for easy access
        attribute.get = get
        attribute.set = set

        if register:
            cls.slots.append(attribute)

    register_attribute = classmethod(register_attribute)

    def register_method(cls, method, method_func, overwrite=False):
        """ Registers a method
        """
        if hasattr(cls, method.name) and not overwrite:
            raise AttributeError('%s already exists in %s' % (method.name, cls.__name__))
        setattr(cls, method.name, meth_func)
        # TODO: This needs work

    register_method = classmethod(register_method)

    def build_methods(cls):
        for attribute in cls.slots:
            cls.register_attribute(attribute, get=attribute.get, set=attribute.set, override=True, register=False)

    build_methods = classmethod(build_methods)

    def __repr__(self):
        key = self._key[1]
        if type(key) in (tuple, list):
            key = [repr(i) for i in key]
        else:
            key = [repr(key)]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(key))

# arch-tag: 246ee465-24a3-4541-a55a-7548356aebfb
