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

from Cerebrum.Utils import Factory

from GroBuilder import GroBuilder
from Builder import Attribute, Method

from Group import Group
from Types import GroupVisibilityType

import Registry
registry = Registry.get_registry()

__all__ = ['Commands']

class Commands(GroBuilder):
    primary_key = []
    slots = []
    method_slots = [
        Method('create_group', Group, [('name', str)], write=True)
    ]

    def __init__(self):
        GroBuilder.__init__(self, cache=None)

    def create_group(self, name):
        db = self.get_database()
        group = Factory.get('Group')(db)
        print 'change_by', [db.change_by]
        group.populate(db.change_by, GroupVisibilityType(name='A').get_id(), name)
        group.write_db()

        id = group.entity_id
        return Group(id, write_lock=self.get_writelock_holder())

registry.register_class(Commands)

# arch-tag: d756f6b2-7b09-4bf5-a65e-81cacfea017a
