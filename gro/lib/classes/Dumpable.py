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

import copy

from GroBuilder import GroBuilder
from Builder import Method, Attribute

from DumpClass import DumpClass, Struct
from SearchClass import SearchClass

import Registry
registry = Registry.get_registry()

def create_mark_method(name, method_name):
    """
    This function creates a simple get method get(self), which
    uses getattr().
    Methods created with this function are used in search objects.
    """

    def dump(self):
        for struct, obj in zip(self.structs, self._objects):
            value = getattr(obj, method_name)()
            struct[name] = value
    return dump

class Dumpable(object):
    def build_dumper_class(cls):
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
            dumper_class.register_method(mark, get, overwrite=True)

        def dump(self):
            return self.structs
        dumper_class.register_method(Method('dump', [Struct(cls)]), dump, overwrite=True)

    build_dumper_class = classmethod(build_dumper_class)

def get_dumper(self):
    return self._cls.dumper_class(self.search())

SearchClass.register_method(Method('get_dumper', DumpClass), get_dumper)

# arch-tag: a16cca29-1212-4dc6-a343-7023e0240b87
