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

from Cerebrum.Utils import Factory
from SpineLib.Builder import Method, Attribute
from SpineLib.DatabaseClass import DatabaseAttr

from CerebrumClass import CerebrumAttr, CerebrumDbAttr
from Cerebrum.Utils import Factory

from Entity import Entity
from Types import EntityType, GroupVisibilityType
from Date import Date
from Commands import Commands

from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['Group']

table = 'group_info'

class Group(Entity):
    slots = Entity.slots + [
        CerebrumDbAttr('description', table, str, write=True),
        CerebrumDbAttr('visibility', table, GroupVisibilityType, write=True),
        CerebrumDbAttr('creator', table, Entity),
        CerebrumDbAttr('create_date', table, Date),
        CerebrumDbAttr('expire_date', table, Date, write=True),
        CerebrumAttr('name', str, write=True)
    ]
    method_slots = Entity.method_slots + [
    ]

    db_attr_aliases = Entity.db_attr_aliases.copy()
    db_attr_aliases[table] = {
        'id':'group_id',
        'creator':'creator_id'
    }

    cerebrum_attr_aliases = {'name':'group_name'}
    cerebrum_class = Factory.get('Group')

    entity_type = 'group'

registry.register_class(Group)

def create(self, name):
    db = self.get_database()
    new_id = Group._create(db, db.change_by, GroupVisibilityType(db, name='A').get_id(), name)
    return Group(db, new_id)

Commands.register_method(Method('create_group', Group, args=[('name', str)], write=True), create)

def get_group_by_name(self, name):
    db = self.get_database()
    s = registry.EntityNameSearcher(db)
    s.set_value_domain(registry.ValueDomain(db, name='group_names'))
    s.set_name(name)

    group, = s.search()
    return group.get_entity()

Commands.register_method(Method('get_group_by_name', Group, args=[('name', str)]), get_group_by_name)

# arch-tag: 263241fc-0255-4c71-9494-dc13153ad781
