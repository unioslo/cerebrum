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

from Builder import Builder

class Registry(object):
    def __init__(self):
        self.map = {}
        self.classes = []

    def register_class(self, cls):
        from Searchable import Searchable
        from Dumpable import Dumpable
        
        name = cls.__name__

        assert not name in self.map

        if issubclass(cls, Builder):
            cls.build_methods()

        if issubclass(cls, Searchable) and issubclass(cls, Builder):
            cls.build_search_class()
            self.register_class(cls.search_class)

        if issubclass(cls, Dumpable) and issubclass(cls, Builder):
            cls.build_dumper_class()
            self.register_class(cls.dumper_class)

        for i in self.classes:
            if issubclass(cls, i):
                cls.builder_parents += (i, )
                i.builder_children += (cls, )

        self.map[name] = cls
        self.classes.append(cls)

    def __getattr__(self, key):
        return self.map[key]

    def build_all(self):
        for i in self.classes:
            i.build_methods()

_registry = None
def get_registry():
    global _registry
    if _registry is None:
        _registry = Registry()
    return _registry

# arch-tag: 3d88e0d4-1147-4562-a8fa-1a627e2ced49
