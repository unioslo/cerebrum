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

from Searchable import Searchable
from Builder import Builder

class Registry(object):
    def __init__(self):
        self.classes = {}

    def register_class(self, gro_class):
        name = gro_class.__name__

        assert not name in self.classes

        if issubclass(gro_class, Builder):
            gro_class.build_methods()

        if issubclass(gro_class, Searchable) and issubclass(gro_class, Builder):
            self.register_class(gro_class.create_search_class())

        self.classes[name] = gro_class

    def get_gro_classes(self):
        gro_classes = {}
        for name, cls in self.classes.items():
            if issubclass(cls, Builder):
                gro_classes[name] = cls
        return gro_classes

    def __getattr__(self, key):
        return self.classes[key]

_registry = None
def get_registry():
    global _registry
    if _registry is None:
        _registry = Registry()
    return _registry

# arch-tag: 3421aaa4-b539-4969-b7d1-6ddf738492f0
