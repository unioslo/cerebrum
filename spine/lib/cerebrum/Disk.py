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
from Host import Host
from Types import EntityType
from Commands import Commands

from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['Disk']

table = 'disk_info'
class Disk(Entity):
    slots = Entity.slots + [
        DatabaseAttr('host', table, Host),
        DatabaseAttr('path', table, str, write=True),
        DatabaseAttr('description', table, str, write=True)
    ]

    method_slots = Entity.method_slots + [
    ]

    db_attr_aliases = Entity.db_attr_aliases.copy()
    db_attr_aliases[table] = {
        'id':'disk_id',
        'host':'host_id'
    }

    cerebrum_class = Factory.get('Disk')
    entity_type = EntityType(name='disk')

registry.register_class(Disk)

def create(self, host, path, description):
    db = self.get_database()
    new_id = Disk._create(db, host.get_id(), path, description)
    
    return Disk(new_id, write_locker=self.get_writelock_holder())

args = [('host', Host), ('path', str), ('description', str)]
Commands.register_method(Method('create_disk', Disk, args=args, write=True), create)

# arch-tag: 3c4a4e7b-88e8-4b38-83b4-8648146d94bf
