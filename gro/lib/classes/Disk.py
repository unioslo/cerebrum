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

import Cerebrum.Disk
import Database

from Entity import Entity
from Builder import Attribute

__all__ = ['Disk']

class Disk(Entity):
    slots = Entity.slots + [Attribute('host', 'Host', writable=True),
                            Attribute('path', 'string', writable=True),
                            Attribute('description', 'string', writable=True)]

    cerebrum_class = Cerebrum.Disk.Disk

    def _load_disk(self):
        import Host
        e = Cerebrum.Disk.Disk(Database.get_database())
        e.find(self._entity_id)

        self._host = Host.Host(int(e.host_id))
        self._path = e.path
        self._description  = e.description

    def _save_disk(self):
        e = Cerebrum.Disk.Disk(Database.get_database())
        e.find(self._entity_id)

        e.host_id = self._host.get_entity_id()
        e.path = self._path
        e.description = self._description
        e.write_db()
        e.commit()


    load_host = load_path = load_description = _load_disk
    save_host = save_path = save_description = _save_disk
