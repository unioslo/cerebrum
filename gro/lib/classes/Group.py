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

from Builder import Method
from DatabaseClass import DatabaseAttr

from Entity import Entity
from Types import EntityType, GroupVisibilityType
from Date import Date

import Registry
registry = Registry.get_registry()

__all__ = ['Group']

table = 'group_info'

class Group(Entity):
    slots = Entity.slots + [
        DatabaseAttr('description', table, str, write=True),
        DatabaseAttr('visibility', table, GroupVisibilityType),
        DatabaseAttr('creator', table, Entity),
        DatabaseAttr('create_date', table, Date),
        DatabaseAttr('expire_date', table, Date)
    ]
    method_slots = Entity.method_slots + [
        Method('get_name', str)
    ]

    db_attr_aliases = Entity.db_attr_aliases.copy()
    db_attr_aliases[table] = {
        'id':'group_id',
        'creator':'creator_id'
    }

    entity_type = EntityType(name='group')

    def get_name(self):
        return registry.EntityName(self, registry.ValueDomain(name='group_names')).get_name()

registry.register_class(Group)

# arch-tag: e485b7a1-290b-467a-a746-761c30b71e13
