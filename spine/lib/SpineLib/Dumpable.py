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

def create_mark_method(name, method_name):
    """
    This function creates a mark method for every attribute and read method in the class.
    Using mark_<something> marks <something> for inclusion in the dump.
    """

    def dump(self):
        holder = self.get_writelock_holder()
        for struct, obj in zip(self.structs, self._objects):
            obj.lock_for_reading(holder)
            value = getattr(obj, method_name)()
            struct[name] = value
    return dump

class Dumpable(object):
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

        for attr in cls.slots:
            get = create_mark_method(attr.name, attr.get_name_get())
            dumper_class.register_method(Method('mark_' + attr.name, None), get, overwrite=True)

        for method in [i for i in cls.method_slots if not i.write]:
            get = create_mark_method(method.name, method.name)
            mark = copy.copy(method)
            mark.name = 'mark_' + mark.name
            mark.data_type = None
            mark.write = True
            dumper_class.register_method(mark, get, overwrite=True)

        def dump(self):
            return self.structs
        m = Method('dump', [Struct(cls)], write=True)
        dumper_class.register_method(m, dump, overwrite=True)

        if issubclass(cls, Searchable):
            get_dump = create_get_dumper(cls.dumper_class)
            m = Method('get_dumper', cls.dumper_class, write=True)
            cls.search_class.register_method(m, get_dump, overwrite=True)

    build_dumper_class = classmethod(build_dumper_class)

def create_get_dumper(dumper_class):
    def get_dumper(self):
        return dumper_class(self.search())
    return get_dumper

# arch-tag: 94dead40-0291-4725-a4dd-a37303eec825
