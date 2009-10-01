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
from Cerebrum.modules import Email
from Cerebrum.modules.no.ntnu.bofhd_auth import BofhdAuth

from lib.data.DTO import DTO
from lib.data.HostDTO import HostDTO
from lib.data.EmailTargetDTO import EmailTargetDTO

Database = Utils.Factory.get("Database")
Constants = Utils.Factory.get("Constants")
Host = Utils.Factory.get("Host")

class HostDAO(object):
    def __init__(self, db=None):
        self.db = db or Database()
        self.auth = BofhdAuth(self.db)
        self.constants = Constants(self.db)

    def get(self, host_id):
        host = Host(self.db)
        host.find(host_id)

        dto = DTO()
        dto.id = host_id
        dto.name = host.name
        dto.type_name = self._get_type_name()
        dto.description = host.description

        self.populate_email_server(host_id, dto)

        return dto

    def populate_email_server(self, entity_id, dto):
        email = Email.EmailServer(self.db)
        try:
            email.find(entity_id)
            dto.is_email_server = True
            dto.email_server_type = self.constants.EmailServerType(email.email_server_type)
        except NotFoundError, e:
            dto.is_email_server = False

    def get_email_servers(self):
        email = Email.EmailServer(self.db)
        for server in email.list_email_server_ext():
            yield HostDTO(server)
    
    def get_email_targets(self, entity_id):
        et = Email.EmailTarget(self.db)
        epa = Email.EmailPrimaryAddressTarget(self.db)
        ea = Email.EmailAddress(self.db)
        es = Email.EmailServer(self.db)

        try:
            et.find_by_target_entity(entity_id)
        except NotFoundError, e:
            return []

        try:
            es.find(et.email_server_id)
        except NotFoundError, e:
            return []

        epa.find(et.entity_id)
        ea.find(epa.email_primaddr_id)
        target_type = self.constants.EmailTarget(et.email_target_type)
        target = EmailTargetDTO(et)
        target.type = target_type.str + "@" + es.name
        target.address = ea.get_address()
        return [target]

    def search(self, name=None, description=None):
        # The data set is small enough that we search within the strings.
        if name:
            name = "*" + name.strip("*") + "*"
        if description:
            description = "*" + description.strip("*") + "*"
        kwargs = {
            'name': name or None,
            'description': description or None,
        }

        hosts = []
        for host in Host(self.db).search(**kwargs):
            dto = DTO.from_row(host)
            dto.id = dto.host_id
            dto.type_name = self._get_type_name()
            hosts.append(dto)
        return hosts

    def save(self, dto):
        host = Host(self.db)
        host.find(dto.id)

        if not self.auth.can_edit_host(self.db.change_by, host):
            raise PermissionDenied("Not authorized to edit host")

        host.name = dto.name
        host.description = dto.description
        host.write_db()

    def create(self, name, description):
        if not self.auth.can_create_host(self.db.change_by):
            raise PermissionDenied("Not authorized to edit host")

        host = Host(self.db)
        host.populate(name, description)
        host.write_db()

        return self.get(host.entity_id)

    def delete(self, host_id):
        host = Host(self.db)
        host.find(host_id)

        if not self.auth.can_delete_host(self.db.change_by, host):
            raise PermissionDenied("Not authorized to view account")

        host.delete()

    def _get_type_name(self):
         return str(self.constants.entity_host)
