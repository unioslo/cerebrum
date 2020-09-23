# -*- coding: utf-8 -*-
#
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
"""
Generic HR import.
"""
import logging

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.automatic_group.structure import update_memberships

from .importer import AbstractImport
from . import models

logger = logging.getLogger(__name__)

LEADER_GROUP_PREFIX = 'adm-leder-'
RESERVATION_GROUP = 'SAP-elektroniske-reservasjoner'


class EmployeeImportBase(AbstractImport):

    @property
    def const(self):
        """ Constants. """
        if not hasattr(self, '_const'):
            self._const = Factory.get('Constants')(self.db)
        return self._const

    @property
    def source_system(self):
        # TODO: Use different source systems?
        return self.const.system_sap

    def create(self, employee_data):
        """ Create a new Person object using employee_data. """
        # TODO: Warn about name matches
        assert employee_data is not None
        person_obj = Factory.get('Person')(self.db)

        gender = self.const.Gender(employee_data.gender)
        person_obj.populate(employee_data.birth_date, gender)
        person_obj.write_db()

        assert person_obj.entity_id
        logger.info('Created person_id=%r from %r',
                    person_obj.entity_id, employee_data)
        self.update(employee_data, person_obj)

    def update(self, employee_data, person_obj):
        """ Update the Person object using employee_data. """
        assert employee_data is not None
        assert person_obj is not None
        assert person_obj.entity_id
        updater = HRDataImport(self.db, employee_data, person_obj,
                               self.source_system)
        updater.import_to_cerebrum()

    def remove(self, person_obj):
        """ Clear HR data from a Person object. """
        assert person_obj is not None
        assert person_obj.entity_id
        # TODO: clear all sap-data (except ext-ids?)


class HRDataImport(object):

    def __init__(self, database, hr_person, cerebrum_person, source_system):
        self.hr_person = hr_person
        self.cerebrum_person = cerebrum_person
        self.database = database
        self.source_system = source_system
        self.co = Factory.get('Constants')(self.database)

    def import_to_cerebrum(self):
        """Call all the update functions, creating or updating a person"""
        logger.info('Starting import_to_cerebrum for %r', self.hr_person.hr_id)
        self.update_person()
        self.update_external_ids()
        self.update_names()
        self.update_titles()
        self.update_contact_info()
        logger.info('Done with import_to_cereburm for %r',
                    self.cerebrum_person.entity_id)

    def update_person(self):
        """Update person with birth date and gender"""
        if self.hr_person.gender:
            self.hr_person.gender = self.co.Gender(self.hr_person.gender)
        else:
            self.hr_person.gender = self.co.gender_unknown
        if not (self.cerebrum_person.gender and
                self.cerebrum_person.birth_date and
                self.cerebrum_person.gender == self.hr_person.gender and
                self.cerebrum_person.birth_date == self.hr_person.birth_date):
            self.cerebrum_person.populate(
                self.hr_person.birth_date,
                self.hr_person.gender)
            self.cerebrum_person.write_db()
            logger.info('Added birth date %r and gender %r for %r',
                        self.hr_person.birth_date,
                        self.hr_person.gender,
                        self.cerebrum_person.entity_id)

    def update_external_ids(self):
        """Update person in Cerebrum with appropriate external ids"""
        hr_external_ids = set()
        for ext_id in self.hr_person.external_ids:
            ext_id.id_type = self.co.EntityExternalId(ext_id.id_type)
            hr_external_ids.add(ext_id)
        self.hr_person.external_ids = hr_external_ids

        cerebrum_external_ids = set()
        for ext_id in self.cerebrum_person.get_external_id(
                source_system=self.source_system):
            cerebrum_external_ids.add(
                models.HRExternalID(
                    self.co.EntityExternalId(ext_id['id_type']),
                    ext_id['external_id'])
            )
        to_remove = cerebrum_external_ids - self.hr_person.external_ids
        to_add = self.hr_person.external_ids - cerebrum_external_ids
        self.cerebrum_person.affect_external_id(
            self.source_system,
            *(ext_id.id_type for ext_id in to_remove | to_add))
        if to_remove:
            logger.info(
                'Purging externalids of types %r for id: %r',
                (unicode(ext_id.id_type)
                 for ext_id in to_remove),
                self.cerebrum_person.entity_id)
        for ext_id in to_add:
            self.cerebrum_person.populate_external_id(
                self.source_system, ext_id.id_type, ext_id.external_id)
            logger.info('Adding externalid %r for id: %r',
                        (unicode(ext_id.id_type), ext_id.external_id),
                        self.cerebrum_person.entity_id)
        self.cerebrum_person.write_db()

    def update_names(self):
        """Update person in Cerebrum with fresh names"""

        def _get_name_type(name_type):
            """Try to get the name of a specific type from cerebrum"""
            try:
                return self.cerebrum_person.get_name(
                    self.source_system, name_type)
            except Errors.NotFoundError:
                return None

        crb_first_name = _get_name_type(self.co.name_first)
        crb_last_name = _get_name_type(self.co.name_last)

        if crb_first_name != self.hr_person.first_name:
            self.cerebrum_person.affect_names(
                self.source_system, self.co.name_first)
            self.cerebrum_person.populate_name(
                self.co.name_first, self.hr_person.first_name)
            logger.info('Changing first name from %r to %r',
                        crb_first_name, self.hr_person.first_name)

        if crb_last_name != self.hr_person.last_name:
            self.cerebrum_person.affect_names(
                self.source_system, self.co.name_last)
            self.cerebrum_person.populate_name(
                self.co.name_last, self.hr_person.last_name)
            logger.info('Changing last name from %r to %r',
                        crb_last_name, self.hr_person.last_name)
        self.cerebrum_person.write_db()

    def update_titles(self):
        """Update person in Cerebrum with work and personal titles"""
        hr_titles = set()
        for t in self.hr_person.titles:
            t.name_variant = self.co.EntityNameCode(t.name_variant)
            t.name_language = self.co.LanguageCode(t.name_language)
            hr_titles.add(t)
        self.hr_person.titles = hr_titles
        cerebrum_titles = set()
        for title in self.cerebrum_person.search_name_with_language(
                entity_id=self.cerebrum_person.entity_id,
                name_variant=[self.co.work_title, self.co.personal_title]):
            cerebrum_titles.add(
                models.HRTitle(
                    self.co.EntityNameCode(title['name_variant']),
                    self.co.LanguageCode(title['name_language']),
                    title['name'])
            )

        for title in self.hr_person.titles - cerebrum_titles:
            self.cerebrum_person.add_name_with_language(
                name_variant=title.name_variant,
                name_language=title.name_language,
                name=title.name,
            )
            logger.info('Adding title %r for id: %r',
                        title.name, self.cerebrum_person.entity_id)
        for title in cerebrum_titles - self.hr_person.titles:
            self.cerebrum_person.delete_name_with_language(
                name_variant=title.name_variant,
                name_language=title.name_language,
                name=title.name,
            )
            logger.info('Removing title %r for id: %r',
                        title.name, self.cerebrum_person.entity_id)

    def update_contact_info(self):
        """Update person in Cerebrum with contact information"""
        hr_contacts = set()
        for c in self.hr_person.contact_infos:
            c.contact_type = self.co.ContactInfo(c.contact_type)
            hr_contacts.add(c)
        self.hr_person.contact_infos = hr_contacts
        cerebrum_contacts = set()
        for contact in self.cerebrum_person.get_contact_info(
                source=self.source_system):
            cerebrum_contacts.add(
                models.HRContactInfo(
                    self.co.ContactInfo(contact['contact_type']),
                    contact['contact_pref'],
                    contact['contact_value'])
            )
        for contact in cerebrum_contacts - self.hr_person.contact_infos:
            self.cerebrum_person.delete_contact_info(
                source=self.source_system,
                contact_type=contact.contact_type,
                pref=contact.contact_pref,
            )
            logger.info('Removing contact %r of type %r with preference %r '
                        'for id: %r',
                        contact.contact_value,
                        contact.contact_type,
                        contact.contact_pref,
                        self.cerebrum_person.entity_id)
        for contact in self.hr_person.contact_infos - cerebrum_contacts:
            self.cerebrum_person.add_contact_info(
                source=self.source_system,
                type=contact.contact_type,
                value=contact.contact_value,
                pref=contact.contact_pref,
            )
            logger.info('Adding contact %r of type %r with preference %r '
                        'for id: %r',
                        contact.contact_value,
                        contact.contact_type,
                        contact.contact_pref,
                        self.cerebrum_person.entity_id)
