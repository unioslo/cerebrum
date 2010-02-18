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

Database = Utils.Factory.get("Database")
Constants = Utils.Factory.get("Constants")

from lib.data.DTO import DTO
from lib.data.EntityDAO import EntityDAO

class EmailDomainDAO(EntityDAO):
    EntityType = Email.EmailDomain

    def get(self, domain_id):
        domain = self._find(domain_id)
        return self._create_dto(domain)

    def search(self, name=None, category=None, description=None):
        name = name or None
        category = category or None
        description = description or None

        obj = self._get_cerebrum_obj()
        dtos = []

        for domain in obj.search(name, description, category):
            dto = DTO.from_row(domain)
            dto.id = dto.domain_id
            dto.name = dto.domain
            dto.type_name = self._get_type_name()
            dto.type_id = self._get_type_id()
            dtos.append(dto)
        return dtos

    def create(self, name, description):
        if not self.auth.can_create_email_domain(self.db.change_by):
            raise PermissionDenied("Not authorized to create email domain")

        domain = self._get_cerebrum_obj()
        domain.populate(name, description)
        domain.write_db()
        return self._create_dto(domain)

    def delete(self, domain_id):
        domain = self._find(domain_id)
        if not self.auth.can_delete_email_domain(self.db.change_by, domain):
            raise PermissionDenied("Not authorized to delete email domain")

        domain.delete()

    def save(self, domain_id, name, description):
        domain = self._find(domain_id)
        if not self.auth.can_edit_email_domain(self.db.change_by, domain):
            raise PermissionDenied("Not authorized to edit email domain")

        domain.email_domain_name = name
        domain.email_domain_description = description
        domain.write_db()

    def set_category(self, domain_id, category_id):
        domain = self._find(domain_id)
        if not self.auth.can_edit_email_domain(self.db.change_by, domain):
            raise PermissionDenied("Not authorized to edit email domain")

        for row in domain.get_categories():
            domain.remove_category(row.fields.category)

        if category_id:
            domain.add_category(category_id)

    def _create_dto(self, domain):
        dto = DTO()
        dto.id = domain.entity_id
        dto.name = self._get_name(domain)
        dto.description = domain.email_domain_description

        dto.categories = [Constants.EmailDomainCategory(r.fields.category)
                            for r in domain.get_categories()]
        dto.category = dto.categories and dto.categories[0] or ""
        dto.type_name = self._get_type_name()
        dto.type_id = self._get_type_id()
        return dto

    def _get_name(self, domain):
        return domain.get_domain_name()

    def _get_type(self):
        return self.constants.entity_email_domain
