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

import CereUtils

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
        DatabaseAttr('description', table, str, write=True),
        DatabaseAttr('visibility', table, GroupVisibilityType, write=True),
        DatabaseAttr('creator', table, Entity),
        DatabaseAttr('create_date', table, Date),
        DatabaseAttr('expire_date', table, Date, write=True),
        Attribute('name', str, write=True)
    ]
    method_slots = Entity.method_slots + [
        Method('delete', None, write=True)
    ]

    db_attr_aliases = Entity.db_attr_aliases.copy()
    db_attr_aliases[table] = {
        'id':'group_id',
        'creator':'creator_id'
    }

    entity_type = EntityType(name='group')

    def load_name(self):
        entityName = registry.EntityName(self, registry.ValueDomain(name='group_names'))
        self._name = entityName.get_name()

    def delete(self):
        db = self.get_database()
        group = Factory.get('Group')(db)
        group.find(self.get_id())
        group.delete()
        self.invalidate()

cls = CereUtils.Factory.get('Group')
Group.save_name = CereUtils.create_save(Group.get_attr('name'), cls, 'group_name')
Group.save_description = CereUtils.create_save(Group.get_attr('description'), cls, 'description')
Group.save_expire_date = CereUtils.create_save(Group.get_attr('expire_date'), cls, 'description')

registry.register_class(Group)

def create(self, name):
    db = self.get_database()
    group = Factory.get('Group')(db)
    group.populate(db.change_by, GroupVisibilityType(name='A').get_id(), name)
    group.write_db()
    return Group(group.entity_id, write_lock=self.get_writelock_holder())

Commands.register_method(Method('create_group', Group, args=[('name', str)], write=True), create)

# arch-tag: 263241fc-0255-4c71-9494-dc13153ad781
