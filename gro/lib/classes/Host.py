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

import Cerebrum.Disk # er det ikke logisk at Host ligger i Disk? :p
import Database


from Entity import Entity
from Builder import Attribute

__all__ = ['Host']

class Host(Entity):
    slots = Entity.slots + [Attribute('name', 'string', writable=True), 
                            Attribute('description', 'string', writable=True)]

    cerebrum_class = Cerebrum.Disk.Host

    def _load_host(self):
        e = Cerebrum.Disk.Host(Database.get_database())
        e.find(self.get_entity_id())

        self._name = e.name
        self._description  = e.description

    def _save_host(self):
        e = Cerebrum.Disk.Host(Database.get_database())
        e.find(self.get_entity_id())
        e.description = self._description
        e.name = self._name
        e.write_db()
        e.commit()

    load_name = _load_host
    load_description = _load_host

    save_name = _save_host
    save_description = _save_host
