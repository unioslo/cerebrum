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

import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError
from Cerebrum.modules.no.ntnu.bofhd_auth import BofhdAuth

from lib.data.DTO import DTO
from lib.data.HostDAO import HostDAO
from lib.data.EntityDAO import EntityDAO

Database = Utils.Factory.get("Database")
Constants = Utils.Factory.get("Constants")
Disk = Utils.Factory.get("Disk")

class DiskDAO(EntityDAO):
    EntityType = Disk

    def __init__(self, *args, **kwargs):
        super(DiskDAO, self).__init__(*args, **kwargs)
        self.host_dao = HostDAO(self.db)

    def get(self, disk_id):
        disk = self._find(disk_id)
        return self._create_dto(disk)

    def _create_dto(self, disk):
        dto = DTO()
        dto.id = disk.entity_id
        dto.type_name = self._get_type_name()
        dto.description = disk.description
        dto.path = disk.path
        dto.name = disk.path
        dto.host = self.host_dao.get(disk.host_id)

        return dto

    def search(self, path=None, description=None, host_id=None):
        # The data set is small enough that we search within the strings.
        if path:
            path = "*" + path.strip("*") + "*"
        if description:
            description = "*" + description.strip("*") + "*"

        kwargs = {
            'path': path or None,
            'description': description or None,
            'host_id': host_id or None,
        }

        disks = []
        for disk in Disk(self.db).search(**kwargs):
            dto = self.get(disk.fields.disk_id)
            disks.append(dto)
        return disks

    def save(self, dto):
        disk = Disk(self.db)
        disk.find(dto.id)

        if not self.auth.can_edit_disk(self.db.change_by, disk):
            raise PermissionDenied("Not authorized to edit disk")

        disk.path = dto.path
        disk.description = dto.description
        disk.write_db()

    def create(self, host_id, path, description):
        if not self.auth.can_create_disk(self.db.change_by):
            raise PermissionDenied("Not authorized to edit disk")

        disk = Disk(self.db)
        disk.populate(host_id, path, description)
        disk.write_db()

        return self.get(disk.entity_id)

    def delete(self, disk_id):
        disk = Disk(self.db)
        disk.find(disk_id)

        if not self.auth.can_delete_disk(self.db.change_by, disk):
            raise PermissionDenied("Not authorized to view account")

        disk.delete()
        
    def _get_type(self):
         return self.constants.entity_disk
