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

from GroBuilder import GroBuilder

import Registry
registry = Registry.get_registry()

class Struct:
    def __init__(self, data_type):
        self.data_type = data_type

class DumpClass(GroBuilder):
    primary = []
    slots = []
    method_slots = []

    def create_primary_key(cls, objects):
        l = [] + objects
        l.sort()
        return (tuple(l), )
    create_primary_key = classmethod(create_primary_key)

    def __init__(self, objects):
        self.structs = []
        self._objects = objects

        for i in objects:
            s = {'reference':i}
            for key, value in zip(i.primary, i.get_primary_key()):
                s[key.name] = value
            self.structs.append(s)

        GroBuilder.__init__(self)

registry.register_class(DumpClass)


# arch-tag: abc1fa9e-df20-4d99-b55e-e8299146105f
