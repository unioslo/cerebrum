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
from CerebrumClass import CerebrumDbAttr

from Entity import Entity
from Host import Host
from Types import EntityType
from Commands import Commands

from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['Disk']

table = 'disk_info'
class Disk(Entity):
    slots = Entity.slots + (
        CerebrumDbAttr('host', table, Host),
        CerebrumDbAttr('path', table, str, write=True),
        CerebrumDbAttr('description', table, str, write=True)
    )
    db_attr_aliases = Entity.db_attr_aliases.copy()
    db_attr_aliases[table] = {
        'id':'disk_id',
        'host':'host_id'
    }

    cerebrum_class = Factory.get('Disk')
    entity_type = 'disk'

registry.register_class(Disk)

def create_disk(self, host, path, description):
    """
    Create a disk.
    \\param host The host that owns the disk
    \\param path The root path of the disk
    \\param description
    \\return Created Disk Object
    """
    db = self.get_database()
    new_id = Disk._create(db, host.get_id(), path, description)
    return Disk(db, new_id)

create_disk.signature = Disk
create_disk.signature_write = True
create_disk.signature_args = [Host, str, str]
Commands.create_disk = create_disk

def get_disks(self):
    """
    \\return List of disks on host
    """
    searcher = registry.DiskSearcher(self.get_database())
    searcher.set_host(self)
    return searcher.search()

get_disks.signature = [Disk]
Host.register_methods([get_disks])

# arch-tag: 3c4a4e7b-88e8-4b38-83b4-8648146d94bf
