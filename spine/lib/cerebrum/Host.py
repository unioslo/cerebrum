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
from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr
from SpineLib.Builder import Method

from Entity import Entity
from Types import EntityType
from Commands import Commands

from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['Host']

table = 'host_info'
class Host(Entity):
    slots = Entity.slots + [
        DatabaseAttr('name', table, str, write=True),
        DatabaseAttr('description', table, str, write=True)
    ]

    method_slots = Entity.method_slots + [
        Method('delete', None, write=True)
    ]

    db_attr_aliases = Entity.db_attr_aliases.copy()
    db_attr_aliases[table] = {
        'id':'host_id'
    }

    entity_type = EntityType(name='host')

    def delete(self):
        db = self.get_database()
        host = Factory.get('Host')(db)
        host.find(self.get_id())
        host.delete()
        self.invalidate()

registry.register_class(Host)

def create(self, name, description):
    db = self.get_database()
    host = Factory.get('Host')(db)
    host.populate(name, description)
    host.write_db()
    return Host(host.entity_id, write_lock=self.get_writelock_holder())
    
args = [('name', str), ('description', str)]
Commands.register_method(Method('create_host', Host, args=args, write=True), create)

# arch-tag: bdad7df2-98cb-43f6-ab57-a9ae34a1c912
