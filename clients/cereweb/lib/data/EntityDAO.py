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
from Cerebrum.modules.no.ntnu.bofhd_auth import BofhdAuth

from lib.data.ConstantsDAO import ConstantsDAO
from lib.data.DTO import DTO
from lib.data.EntityDTO import EntityDTO
from lib.data.ExternalIdDAO import ExternalIdDAO
import mx.DateTime

Database = Utils.Factory.get("Database")
Constants = Utils.Factory.get("Constants")
Entity = Utils.Factory.get("Entity")

class EntityDAO(object):
    EntityType = None

    def __init__(self, db=None):
        self.db = db or Database()
        self.constants = Constants(self.db)
        self.auth = BofhdAuth(self.db)

    def get(self, entity_id):
        raise NotImplementedError("This method should be overloaded.")

    def get_by_name(self, name):
        raise NotImplementedError("This method should be overloaded.")

    def get_entity(self, entity_id):
        try:
            entity = self._find(entity_id)
        except NotFoundError, e:
            return self._create_null_object(entity_id)
        return self._create_entity_dto(entity)

    def _create_null_object(self, entity_id):
        dto = EntityDTO()
        dto.id = entity_id
        dto.name = "Not found"
        dto.type_name = self._get_type_name()
        dto.type_id = self._get_type_id()
        return dto

    def get_entity_by_name(self, name):
        entity = self._find_by_name(name)
        return self._create_entity_dto(entity)

    def exists(self, entity_id):
        try:
            entity = Entity(self.db)
            entity.find(entity_id)
        except NotFoundError, e:
            return False
        return True

    def add_external_id(self, entity_id, external_id, external_id_type):
        entity = self._find(entity_id)
        if not self.auth.can_edit_external_id(self.db.change_by, entity, external_id_type):
            raise PermissionDenied("Not authorized to edit external id of entity (%s)" % entity_id)

        source = self.constants.AuthoritativeSystem("Manual")
        id_type = self.constants.EntityExternalId(external_id_type)

        entity.affect_external_id(source, id_type)
        entity.populate_external_id(source, id_type, external_id)
        entity.write_db()

    def remove_external_id(self, entity_id, external_id_type):
        entity = self._find(entity_id)
        if not self.auth.can_edit_external_id(self.db.change_by, entity, external_id_type):
            raise PermissionDenied("Not authorized to edit external id of entity (%s)" % entity_id)

        source = self.constants.AuthoritativeSystem("Manual")
        id_type = self.constants.EntityExternalId(external_id_type)

        entity.affect_external_id(source, id_type)
        entity.write_db()

    def add_spread(self, entity_id, spread):
        entity = self._find(entity_id)
        spread_type = self.constants.Spread(spread)

        if not self.auth.can_edit_spread(self.db.change_by, entity,
                                         int(spread_type)):
            raise PermissionDenied("Not authorized to edit spread (%s) of entity (%s)" % (spread, entity_id))

        entity.add_spread(spread_type)
        entity.write_db()

    def remove_spread(self, entity_id, spread):
        entity = self._find(entity_id)
        spread_type = self.constants.Spread(spread)

        if not self.auth.can_edit_spread(self.db.change_by, entity,
                                         int(spread_type)):
            raise PermissionDenied("Not authorized to edit spread (%s) of entity (%s)" % (spread, entity_id))

        entity.delete_spread(spread_type)
        entity.write_db()

    def add_quarantine(self, entity_id, quarantine_type, description=None,
                      start_date=None, end_date=None, disable_until=None):
        entity = self._find(entity_id)
        if not self.auth.can_edit_quarantine(self.db.change_by, entity, quarantine_type):
            raise PermissionDenied("Not authorized to edit quarantine (%s) of entity (%s)" % (quarantine_type, entity_id))
        if start_date is None:
            start_date=mx.DateTime.now()
        quarantine_type_id = self.constants.Quarantine(quarantine_type)
        entity.add_entity_quarantine(quarantine_type_id, self.db.change_by,
                                     description, start_date, end_date)
        if disable_until is not None:
            entity.disable_entity_quarantine(quarantine_type_id, disable_until)

    def remove_quarantine(self, entity_id, quarantine_type):
        entity = self._find(entity_id)
        if not self.auth.can_edit_quarantine(self.db.change_by, entity, quarantine_type):
            raise PermissionDenied("Not authorized to edit quarantine (%s) of entity (%s)" % (quarantine_type, entity_id))
        quarantine_type_id = self.constants.Quarantine(quarantine_type)
        entity.delete_entity_quarantine(quarantine_type_id)

    def disable_quarantine(self, entity_id, quarantine_type, disable_until):
        # Disabling of quarantines can be available to admins not allowed to
        # set or remove the quarantine. This should really be constrained by
        # a time limit.
        entity = self._find(entity_id)
        if not self.auth.can_disable_quarantine(self.db.change_by, entity, quarantine_type):
            raise PermissionDenied("Not authorized to edit quarantine (%s) of entity (%s)" % (quarantine_type, entity_id))
        quarantine_type_id = self.constants.Quarantine(quarantine_type)
        entity.disable_entity_quarantine(quarantine_type_id, disable_until)

    def add_note(self, entity_id, subject, body=None):
        entity = self._find(entity_id)
        if not self.auth.can_add_note(self.db.change_by, entity):
            raise PermissionDenied("Not authorized to add note")

        entity.add_note(self.db.change_by, subject, body)

    def delete_note(self, entity_id, note_id):
        entity = self._find(entity_id)
        if not self.auth.can_delete_note(self.db.change_by, entity):
            raise PermissionDenied("Not authorized to delete note")

        entity.delete_note(self.db.change_by, note_id)

    def _get_name(self, entity):
        return "Unknown"

    def _get_type(self):
        """
        Overload to return the Cerebrum Core Type of the Entity.
        """
        return None

    def _get_type_id(self):
        core_type = self._get_type()
        if core_type is None:
            raise NotImplementedError, "This method or _get_type must be overloaded."
        return int(core_type)

    def _get_type_name(self):
        core_type = self._get_type()
        if core_type is None:
            raise NotImplementedError, "This method or _get_type must be overloaded."
        return str(core_type)

    def _get_cerebrum_obj(self):
        if self.EntityType is None:
            raise NotImplementedError(
                "EntityType not set.  Most likely you're not using a valid subclass of EntityDAO.")
        entity = self.EntityType(self.db)
        return entity
        
    def _find(self, entity_id):
        entity = self._get_cerebrum_obj()
        entity.find(entity_id)
        return entity

    def _find_by_name(self, name):
        entity = self._get_cerebrum_obj()
        entity.find_by_name(name)
        return entity

    def _create_entity_dto(self, entity):
        dto = EntityDTO()
        dto.id = entity.entity_id
        dto.name = self._get_name(entity)
        dto.type_name = self._get_type_name()
        dto.type_id = self._get_type_id()
        return dto

    def _get_contacts(self, entity):
        contacts = {}

        for contact in entity.get_contact_info():
            key = "%s:%s" % (contact['contact_type'], contact['contact_value'])
            if not key in contacts:
                dto = DTO()
                dto.value = contact['contact_value']
                dto.variant = ConstantsDAO(self.db).get_contact_type(contact['contact_type'])
                dto.source_systems = []
                contacts[key] = dto

            dto = contacts[key]
            source_system = ConstantsDAO(self.db).get_source_system(contact['source_system'])
            source_system.preferance = contact['contact_pref']
            if not source_system in dto.source_systems:
                dto.source_systems.append(source_system)
        return contacts.values()

    def _get_addresses(self, entity):
        addresses = {}

        for address in entity.get_entity_address():
            key = "%s:%s.%s.%s.%s.%s" % (
                address['address_type'],
                address['address_text'],
                address['p_o_box'],
                address['postal_number'],
                address['city'],
                address['country'])
            if not key in addresses:
                dto = DTO()
                dto.value = DTO()
                dto.value.address_text = address['address_text']
                dto.value.p_o_box = address['p_o_box']
                dto.value.postal_number = address['postal_number']
                dto.value.city = address['city']
                dto.value.country = address['country']
                dto.variant = ConstantsDAO(self.db).get_address_type(address['address_type'])
                dto.source_systems = []
                addresses[key] = dto

            dto = addresses[key]
            source_system = ConstantsDAO(self.db).get_source_system(address['source_system'])
            if not source_system in dto.source_systems:
                dto.source_systems.append(source_system)
        return addresses.values()

    def _get_external_ids(self, entity):
        return ExternalIdDAO(self.db).create_from_entity(entity)

    def _get_spreads(self, entity):
        spreads = []
        spread_dao = ConstantsDAO(self.db)
        for spread in entity.get_spread():
            dto = spread_dao.get_spread(spread['spread'])
            spreads.append(dto)
        return spreads

