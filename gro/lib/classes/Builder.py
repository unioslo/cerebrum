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

from Caching import Caching
from Locking import Locking

__all__ = ['Attribute', 'Method', 'Builder', 'CorbaBuilder']


class Attribute:
    def __init__(self, name, data_type, writable=False):
        self.type = 'Attribute'
        self.name = name
        self.data_type = data_type
        self.writable = writable

        self.get = None
        self.set = None

    def __repr__(self):
        return '%s(%s, %s)' % (self.__class__.__name__, `self.name`, `self.data_type`)

class Method:
    def __init__(self, name, data_type, args=[], exceptions=[], apHandler=False):
        self.type = 'Method'
        self.name = name
        self.data_type = data_type
        self.args = args
        self.apHandler = apHandler

    def __repr__(self):
        return '%s(%s, %s)' % (self.__class__.__name__, `self.name`, `self.data_type`)

# å bruke en klasse med __call__ vil ikke funke, da den ikke vil bli bundet til objektet.
# mulig det kan jukses til med noen stygge metaklassetriks, men dette blir penere.

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
            if value is lazy:
                raise Exception('%s was not initialized during load' % var)
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

class CorbaBuilder:
#    def create_idl_class(cls):
#        # TODO: bør vi legge CorbaBuilder i en egen fil?
#        idl_string = cls.create_idl('generated') # TODO: hvor skal generert idl havne?
#        import sys
#        import omniORB
#        omniORB.importIDLString(idl_string)
#
#        idl_class = getattr(sys.modules['generated'], cls.__name__)
#        return idl_class

    def create_idl(cls, module_name=None):
        txt = cls.create_idl_header()
        txt += cls.create_idl_interface()

        if module_name is not None:
            return 'module %s {\n\t%s\n};' % (module_name, txt.replace('\n', '\n\t'))
        else:
            return txt

    def create_idl_header(cls, defined = None):
        if defined is None:
            defined = []

        txt = ''

#        txt = 'interface %s;\n' % cls.__name__
#        txt += 'typedef sequence<%s> %sSeq;\n' % (cls.__name__, cls.__name__)

        # TODO. this is a bit nasty

        for slot in cls.slots + cls.method_slots:
            if not slot.data_type[0].isupper():
                continue
            if slot.data_type.endswith('Seq'):
                name = slot.data_type[:-3]
            else:
                name = slot.data_type

            if name in defined:
                continue
            else:
                defined.append(name)
            txt += 'interface %s;\n' % name
            txt += 'typedef sequence<%s> %sSeq;\n' % (name, name)

        return txt

    def create_idl_interface(cls):
        txt = 'interface %s {\n' % cls.__name__

        txt += '\t//constructors\n'
#        txt += '\t%s get_object(%s);\n' % (cls.__name__, ', '.join(['in %s %s' % (attr.data_type, attr.name) for attr in cls.primary]))

        txt += '\n\t//get and set methods for attributes\n'
        for attr in cls.slots:
            txt += '\t%s get_%s();\n' % (attr.data_type, attr.name)
            if attr.writable:
                txt += '\tvoid set_%s(in %s new_%s);\n' % (attr.name, attr.data_type, attr.name)
            txt += '\n'

        txt += '\n\t//other methods\n'
        for method in cls.method_slots:
            args = ['in %s %s' % (attr.data_type, attr.name) for attr in method.args]
            txt += '\t%s %s(%s);\n' % (method.data_type, method.name, ', '.join(args))

        txt += '};\n'

        return txt

    create_idl = classmethod(create_idl)
    create_idl_header = classmethod(create_idl_header)
    create_idl_interface = classmethod(create_idl_interface)
 

class Builder(Caching, Locking, CorbaBuilder):
    primary = []
    slots = []
    method_slots = []

    def __init__(self, *args, **vargs):
        cls = self.__class__
        mark = '_%s%s' % (cls.__name__, id(self))
        # check if the object is old
        if hasattr(self, mark):
            return getattr(self, mark)
        
        Locking.__init__(self)
        Caching.__init__(self)

        self.prepare() # FIXME: finne på noe lurt her

        slotNames = [i.name for i in cls.slots]
        # set all variables give in args and vargs
        for var, value in zip(slotNames, args) + vargs.items():
            setattr(self, '_' + var, value)

        # used to track changes
        if not hasattr(self, 'updated'):
            self.updated = sets.Set()

        # mark the object as old
        setattr(self, mark, time.time())

    def load(self):
        # vil vi ha dette?
        # load kan laste _alle_ attributter vel å iterere gjennom slots...
        raise NotImplementedError('this should not happen')

    def save(self):
        """ Save all changed attributes """

        for var in self.updated:
            getattr(self, 'save_' + var)()
        self.updated.clear()

    def reload(self):
        """ Reload all changed attributes """

        for var in self.updated:
            getattr(self, 'load_' + var)()
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

        If attribute is not writable, save will not be used.
        """

        var_private = '_' + attribute.name
        var_get = 'get_' + attribute.name
        var_set = 'set_' + attribute.name
        var_load = 'load_' + attribute.name
        var_save = 'save_' + attribute.name

        if get is None:
            get = create_lazy_get_method(var_private, var_load)

        if set is None:
            if attribute.writable:
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

    def register_method(cls, method, method_func, overwrite=False):
        """ Registers a method
        """
        if hasattr(cls, method.name) and not overwrite:
            raise AttributeError('%s already exists in %s' % (method.name, cls.__name__))
        setattr(cls, method.name, meth_func)
        # TODO: This needs work

    def prepare(cls):
        for attribute in cls.slots:
            cls.register_attribute(attribute, get=attribute.get, set=attribute.set, override=True, register=False)

    create_primary_key = classmethod(create_primary_key)
    register_attribute = classmethod(register_attribute)
    prepare = classmethod(prepare)

    def __repr__(self):
        key = self._key[1]
        if type(key) in (tuple, list):
            key = [repr(i) for i in key]
        else:
            key = [repr(key)]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(key))
