# -*- coding: utf-8 -*-
# Copyright 2020 University of Oslo, Norway
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

# from Cerebrum.DatabaseAccessor import DatabaseAccessor

from Cerebrum import Errors
from Cerebrum.modules.hr_import import models
from Cerebrum.modules.automatic_group.structure import update_memberships
from Cerebrum.Utils import Factory

LEADER_GROUP_PREFIX = 'adm-leder-'


class HRDataImport(object):

    def __init__(self, database, hr_person, cerebrum_person):
        self.hr_person = hr_person
        self.cerebrum_person = cerebrum_person
        self.database = database
        self.source_system = hr_person.source_system

    def import_to_cerebrum(self):
        """Call all the update functions, creating or updating a person"""
        self.update_person()
        self.update_external_ids()
        self.update_names()
        self.update_affiliations()
        self.update_addresses()
        self.update_titles()
        self.update_leader_groups()
        self.update_contact_info()
        self.update_reservation()

    def update_person(self):
        """Update person with birth date and gender"""
        if not (self.cerebrum_person.gender and
                self.cerebrum_person.birth_date and
                self.cerebrum_person.gender == self.hr_person.gender and
                self.cerebrum_person.birth_date == self.hr_person.birth_date):
            self.cerebrum_person.populate(
                self.hr_person.birth_date,
                self.hr_person.gender)
            self.cerebrum_person.write_db()

    def update_external_ids(self):
        """Update person in Cerebrum with appropriate external ids"""
        cerebrum_external_ids = set()
        for ext_id in self.cerebrum_person.get_external_id(
                source_system=self.source_system):
            cerebrum_external_ids.add(
                models.HRExternalID(
                    ext_id['id_type'],
                    ext_id['external_id'])
            )
        to_remove = cerebrum_external_ids - self.hr_person.external_ids
        to_add = self.hr_person.external_ids - cerebrum_external_ids
        self.cerebrum_person.affect_external_id(
            self.source_system,
            *(ext_id.id_type for ext_id in to_remove | to_add))
        for (id_type, ext_id) in to_add:
            self.cerebrum_person.populate_external_id(
                self.source_system, id_type, ext_id)
        self.cerebrum_person.write_db()

    def update_names(self):
        """Update person in Cerebrum with fresh names"""

        def _get_name_type(self, name_type):
            """Try to get the name of a specific type from cerebrum"""
            try:
                return self.cerebrum_person.get_name(
                    self.source_system, name_type)
            except Errors.NotFoundError:
                return None

        co = Factory.get('Constants')(self.database)
        crb_first_name = _get_name_type(co.name_first)
        crb_last_name = _get_name_type(co.name_last)

        if crb_first_name != self.hr_person.first_name:
            self.cerebrum_person.affect_names(
                self.source_system, co.name_first)
            self.cerebrum_person.populate_name(
                co.name_first, self.hr_person.first_name)

        if crb_last_name != self.hr_person.last_name:
            self.cerebrum_person.affect_names(
                self.source_system, co.name_last)
            self.cerebrum_person.populate_name(
                co.name_last, self.hr_person.last_name)
        self.cerebrum_person.write_db()

    def update_affiliations(self):
        """Update person in Cerebrum with the latest affiliations"""
        cerebrum_affiliations = set()
        for aff in self.cerebrum_person.list_affiliations(
                person_id=self.cerebrum_person.entity_id,
                source_system=self.source_system):
            cerebrum_affiliations.add(
                models.HRAffiliation(
                    aff['ou_id'],
                    aff['affiliation'],
                    aff['status'],
                    precedence=aff['precedence'])
            )
        for aff in cerebrum_affiliations - self.hr_person('affiliations'):
            self.cerebrum_person.delete_affiliation(
                ou_id=aff['ou_id'],
                affiliation=aff['affiliation'],
                source=self.source_system)
        for aff in self.hr_person('affiliations'):
            self.cerebrum_person.populate_affiliation(
                source_system=self.source_system,
                ou_id=aff['ou_id'],
                affiliation=aff['affiliation'],
                status=aff['status'],
                precedence=aff['precedence']
            )
        self.cerebrum_person.write_db()

    def update_addresses(self):
        """Update a person in Cerebrum with addresses"""
        cerebrum_addresses = set()
        for add in self.cerebrum_person.get_entity_address(
                source=self.source_system):
            cerebrum_addresses.add(
                models.HRAddress(
                    add['address_type'],
                    add['city'],
                    add['postal_number'],
                    add['address_text'])
            )

        for add in cerebrum_addresses - self.hr_person.addresses:
            self.cerebrum_person.delete_entity_address(
                source_type=self.source_system,
                a_type=add.address_type
            )
        for add in self.hr_person.addresses - cerebrum_addresses:
            self.cerebrum_person.add_entity_address(
                source=self.source_system,
                type=add.address_type,
                address_text=add.address_text,
                postal_number=add.postal_code,
                city=add.city
            )

    def update_titles(self):
        """Update person in Cerebrum with work and personal titles"""
        co = Factory.get('Constants')(self.database)
        cerebrum_titles = set()
        for title in self.cerebrum_person.search_name_with_language(
                entity_id=self.cerebrum_person.entity_id,
                name_variant=[co.work_title, co.personal_title]):
            cerebrum_titles.add(
                models.HRTitle(
                    title['name_variant'],
                    title['name_language'],
                    title['name'])
            )

        for title in self.hr_person.titles - cerebrum_titles:
            self.cerebrum_person.add_name_with_language(
                name_variant=title.name_variant,
                name_language=title.name_language,
                name=title.name,
            )
        for title in cerebrum_titles - self.hr_person.titles:
            self.cerebrum_person.delete_name_with_language(
                name_variant=title.name_variant,
                name_language=title.name_language,
                name=title.name,
            )

    def update_leader_groups(self):
        """Update leader group memberships for person in Cerebrum"""
        gr = Factory.get('Group')(self.database)
        co = Factory.get('Constants')(self.database)
        cerebrum_memberships = set(
            group['group_id'] for group in gr.search(
                member_id=self.cerebrum_person.entity_id,
                name=LEADER_GROUP_PREFIX + '*',
                group_type=co.group_type_affiliation,
                filter_expired=True,
                fetchall=False)
        )
        update_memberships(
            gr,
            self.cerebrum_person.entity_id,
            cerebrum_memberships,
            self.hr_person.leader_groups)

    def update_contact_info(self):
        """Update person in Cerebrum with contact information"""
        cerebrum_contacts = set()
        for contact in self.cerebrum_person.get_contact_info(
                source=self.source_system):
            cerebrum_contacts.add(
                models.HRAddress(
                    contact['type'],
                    contact['pref'],
                    contact['value'])
            )

        for contact in cerebrum_contacts - self.hr_person.contact_infos:
            self.cerebrum_person.delete_contact_info(
                source_type=self.source_system,
                contact_type_type=contact.contact_type,
                pref=contact.contact_pref,
            )
        for contact in self.hr_person.contact_infos - cerebrum_contacts:
            self.cerebrum_person.add_contact_info(
                source=self.source_system,
                type=contact.address_type,
                value=contact.contact_value,
                pref=contact.contact_pref,
            )

    def update_reservation(self):
        """Manage reservation from public display for person in Cerebrum"""
        gr = Factory.get('Group')(self.database)
        gr.find_by_name('SAP-elektroniske-reservasjoner')
        in_reserved_group = gr.has_member(self.cerebrum_person.entity_id)
        if self.hr_person.reserved and not in_reserved_group:
            gr.add_member(self.cerebrum_person.entity_id)
        elif not self.hr_person.get('reserved') and in_reserved_group:
            gr.remove_member(self.cerebrum_person.entity_id)
