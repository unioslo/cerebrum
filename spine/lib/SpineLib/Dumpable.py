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

import copy

from Builder import Method, Attribute

from sets import Set

__all__ = ['Dumpable']

def create_mark_method(name, method_name, optional=False, attr=None):
    """
    This function creates a mark method for every attribute and read method in the class.
    Using mark_<something> marks <something> for inclusion in the dump.
    """

    def dump(self):
        holder = self.get_writelock_holder()
        for obj in self._objects:
            obj.lock_for_reading(holder)


        if attr is not None:
            objects = [i for i in self._objects if not hasattr(i, attr.get_name_private())]
            if len(objects) > 100:
                self.cls.search_class().search()

        for struct, obj in zip(self.structs, self._objects):
            if optional:
                struct['%s_exists' % name] = True
            try:
                value = getattr(obj, method_name)()
                struct[name] = value
            except Exception, e:
                if optional:
                    struct['%s_exists' % name] = False
                else:
                    raise e

    return dump

class Dumpable(object):
    """Mixin class for adding dumperobjects.
    
    Mixin class which adds generating of dumperobjects, which can be
    used to read many attributes/methods in one method-call.

    The new generated class has methods for marking which attributes and
    methods you want returned, and can then be asked to return them all
    at once, in structs.
    """
    
    def build_dumper_class(cls):
        from DumpClass import DumpClass, Struct
        from Searchable import Searchable

        dumper_class_name = '%sDumper' % cls.__name__
        if not hasattr(cls, 'dumper_class') or dumper_class_name != cls.dumper_class.__name__:
        
            exec 'class %s(DumpClass):\n\tpass\ncls.dumper_class = %s\n' % ( 
                dumper_class_name, dumper_class_name)
                
        dumper_class = cls.dumper_class
            
        dumper_class.cls = cls
        
        dumper_class.primary = [Attribute('objects', [cls])]
        dumper_class.slots = DumpClass.slots + []
        dumper_class.method_slots = DumpClass.method_slots + []

        # mark methods for attributes and methods
        
        for attr in cls.slots:
            get = create_mark_method(attr.name, attr.get_name_get(), attr.optional, attr)
            dumper_class.register_method(Method('mark_' + attr.name, None, write=True), get, overwrite=True)

        for method in cls.method_slots:
            if method.write or method.args:
                continue
            get = create_mark_method(method.name, method.name)
            mark = copy.copy(method)
            mark.name = 'mark_' + mark.name
            mark.data_type = None
            mark.write = True
            dumper_class.register_method(mark, get, overwrite=True)


        # dumper methods for attributes and methods

        for attr in cls.slots:
            if type(attr.data_type) == type(Dumpable) and issubclass(attr.data_type, Dumpable):
                name = 'dump_%s' % attr.name
                m, get_dump = create_generic_dumper(attr.data_type.dumper_class, name, attr.get_name_get(), attr.optional)
                dumper_class.register_method(m, get_dump, overwrite=True)

        for method in cls.method_slots:
            if not method.write and not method.args and type(method.data_type) == type(Dumpable) and issubclass(method.data_type, Dumpable):
                name = 'dump_%s' % method.name
                m, get_dump = create_generic_dumper(method.data_type.dumper_class, name, method.name)
                dumper_class.register_method(m, get_dump, overwrite=True)

        # make dump accessable from search classes
        def dump(self):
            return self.structs
        m = Method('dump', [Struct(cls)], write=True)
        dumper_class.register_method(m, dump, overwrite=True)

        if issubclass(cls, Searchable):
            get_dump = create_get_dumper(dumper_class)
            m = Method('get_dumper', dumper_class, write=True)
            cls.search_class.register_method(m, get_dump, overwrite=True)

    build_dumper_class = classmethod(build_dumper_class)

def create_get_dumper(dumper_class):
    def get_dumper(self):
        return dumper_class(self.search())
    return get_dumper

def create_generic_dumper(dumper_class, name, method_name, optional=False):
    m = Method(name, dumper_class, write=True)
    def get_dumper(self):
        holder = self.get_writelock_holder()
        objects = Set()
        for i in self._objects:
#            i.lock_for_reading(holder)
            if optional:
                try:
                    value = getattr(i, method_name)()
                except:
                    continue
            else:
                value = getattr(i, method_name)()
            objects.add(value)

        return dumper_class(objects)

    return m, get_dumper


# arch-tag: 94dead40-0291-4725-a4dd-a37303eec825
