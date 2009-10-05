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
from Cerebrum.modules.bofhd.errors import PermissionDenied
from Cerebrum.modules.Cereweb import CerewebMotd
from Cerebrum.modules.no.ntnu.bofhd_auth import BofhdAuth

Database = Utils.Factory.get("Database")

from lib.data.DTO import DTO

class MotdDAO(object):
    def __init__(self, db=None):
        self.db = db or Database()
        from lib.data.EntityFactory import EntityFactory
        self.factory = EntityFactory(self.db)
        self.auth = BofhdAuth(self.db)

    def get(self, eid):
        motd = CerewebMotd(self.db)
        motd.find(eid)
        dto = DTO.from_obj(motd)
        dto.creator = self.factory.get_entity(dto.creator, 'account')
        dto.id = dto.motd_id
        return dto

    def get_latest(self, num=None):
        motds = CerewebMotd(self.db).list_motd()
        motds.sort(key=lambda x: x.create_date, reverse=True)
        if num:
            motds = motds[:num]

        result = []
        for motd in motds:
            dto = DTO.from_row(motd)
            dto.id = dto.motd_id
            dto.creator = self.factory.get_entity(dto.creator, 'account')
            result.append(dto)
        return result

    def delete(self, id):
        if not self.auth.can_edit_motd(self.db.change_by):
            raise PermissionDenied("Not authorized to edit motd")

        motd = CerewebMotd(self.db)
        motd.find(id)
        motd.delete()

    def create(self, subject, message):
        if not self.auth.can_edit_motd(self.db.change_by):
            raise PermissionDenied("Not authorized to edit motd")

        motd = CerewebMotd(self.db)
        motd.populate(self.db.change_by, subject, message)
        motd.write_db()
