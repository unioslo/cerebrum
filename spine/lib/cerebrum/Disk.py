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

from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr

from Entity import Entity
from Host import Host
from Types import EntityType

from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['Disk']

table = 'disk_info'
class Disk(Entity):
    slots = Entity.slots + [
        DatabaseAttr('host', table, Host),
        DatabaseAttr('path', table, str),
        DatabaseAttr('description', table, str)
    ]

    db_attr_aliases = Entity.db_attr_aliases.copy()
    db_attr_aliases[table] = {
        'id':'disk_id',
        'host':'host_id'
    }

    entity_type = EntityType(name='disk')
registry.register_class(Disk)

# arch-tag: 3c4a4e7b-88e8-4b38-83b4-8648146d94bf
