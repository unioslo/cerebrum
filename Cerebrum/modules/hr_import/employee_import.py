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

import six

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.date import get_date

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

    def create(self, employee_data):
        """ Create a new Person object using employee_data. """
        # TODO: Warn about name matches
        assert employee_data is not None
        person_obj = Factory.get('Person')(self.db)

        gender = self.const.Gender(employee_data.gender)
        if employee_data.birth_date is None:
            raise ValueError('No birth date, unable to create!')
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
        updater = HRDataImport(self.db, self.mapper.source_system)
        updater.update_person(person_obj, employee_data)

    def remove(self, person_obj):
        """ Clear HR data from a Person object. """
        assert person_obj is not None
        assert person_obj.entity_id
        # TODO: clear all sap-data (except ext-ids?)


class HRDataImport(object):

    def __init__(self, database, source_system):
        """
        :param database:
        :param source_system:
        :param callbacks:
            A series of callbacks to call on changes.
        """
        self.database = database
        self.source_system = source_system
        self.co = Factory.get('Constants')(self.database)

    def update_person(self, db_person, hr_person):
        """Call all the update functions, creating or updating a person"""
        logger.info('Starting update_person for %r', hr_person)
        self.update_basic(db_person, hr_person)
        self.update_external_ids(db_person, hr_person)
        self.update_names(db_person, hr_person)
        self.update_titles(db_person, hr_person)
        self.update_contact_info(db_person, hr_person)
        self.update_affiliations(db_person, hr_person)
        logger.info('Done with update_person for %r',
                    db_person.entity_id)

    def update_basic(self, db_person, hr_person):
        """Update person with birth date and gender"""
        if hr_person.gender:
            gender = self.co.Gender(hr_person.gender)
        else:
            gender = self.co.gender_unknown

        if db_person.gender != gender:
            db_person.gender = gender
            logger.info('Updated gender for person_id=%r', db_person.entity_id)

        if hr_person.birth_date is None:
            logger.warning('No HR birth date for person_id=%r (%r)',
                           db_person.entity_id, hr_person)
        elif get_date(db_person.birth_date) != hr_person.birth_date:
            db_person.birth_date = hr_person.birth_date
            logger.info('Updated birth_date for person_id=%r',
                        db_person.entity_id)

        db_person.write_db()

    def update_external_ids(self, db_person, hr_person):
        """Update person in Cerebrum with appropriate external ids"""
        hr_ids = set(
            (self.co.EntityExternalId(i.id_type), i.external_id)
            for i in hr_person.external_ids)
        db_ids = set(
            (self.co.EntityExternalId(r['id_type']), r['external_id'])
            for r in db_person.get_external_id(
                source_system=self.source_system))

        # All id-types that only exist in one of the sets
        to_remove = set(t[0] for t in db_ids) - set(t[0] for t in hr_ids)
        to_add = set(t[0] for t in hr_ids) - set(t[0] for t in db_ids)

        # All id-types in both sets that differ in *value*
        to_update = set(t[0] for t in (hr_ids - db_ids)) - to_add

        if not any(to_remove | to_add | to_update):
            logger.debug('No change in external_id for person_id=%r',
                         db_person.entity_id)
            return

        logger.info('Updating external_id for person_id=%r: '
                    'add=%r, update=%r, remove=%r',
                    db_person.entity_id,
                    sorted(six.text_type(c) for c in to_add),
                    sorted(six.text_type(c) for c in to_update),
                    sorted(six.text_type(c) for c in to_remove))

        db_person.affect_external_id(
            self.source_system,
            *(to_remove | to_add | to_update))
        for id_type, id_value in hr_ids:
            db_person.populate_external_id(
                self.source_system, id_type, id_value)
        db_person.write_db()

    def update_names(self, db_person, hr_person):
        """Update person in Cerebrum with fresh names"""

        def _get_name_type(name_type):
            """Try to get the name of a specific type from cerebrum"""
            try:
                return db_person.get_name(self.source_system, name_type)
            except Errors.NotFoundError:
                return None

        crb_first_name = _get_name_type(self.co.name_first)
        crb_last_name = _get_name_type(self.co.name_last)

        if crb_first_name != hr_person.first_name:
            db_person.affect_names(self.source_system, self.co.name_first)
            db_person.populate_name(self.co.name_first, hr_person.first_name)
            logger.info('Updating name %s for person with person_id %r',
                        self.co.name_first, db_person.entity_id)
            db_person.write_db()

        if crb_last_name != hr_person.last_name:
            db_person.affect_names(self.source_system, self.co.name_last)
            db_person.populate_name(self.co.name_last, hr_person.last_name)
            logger.info('Updating name %s for person with person_id %r',
                        self.co.name_last, db_person.entity_id)
            db_person.write_db()

    def update_titles(self, db_person, hr_person):
        """Update person in Cerebrum with work and personal titles"""
        hr_titles = set(
            models.HRTitle(
                self.co.EntityNameCode(t.name_variant),
                self.co.LanguageCode(t.name_language),
                t.name)
            for t in hr_person.titles)

        cerebrum_titles = set(
            models.HRTitle(
                self.co.EntityNameCode(row['name_variant']),
                self.co.LanguageCode(row['name_language']),
                row['name'])
            for row in db_person.search_name_with_language(
                entity_id=db_person.entity_id,
                name_variant=[self.co.work_title, self.co.personal_title]))

        for title in hr_titles - cerebrum_titles:
            db_person.add_name_with_language(
                name_variant=title.name_variant,
                name_language=title.name_language,
                name=title.name,
            )
            logger.info('Setting title %s/%s for person_id=%r',
                        title.name_variant, title.name_language,
                        db_person.entity_id)

        # TODO: This will delete titles that we just changed!
        for title in cerebrum_titles - hr_titles:
            db_person.delete_name_with_language(
                name_variant=title.name_variant,
                name_language=title.name_language,
                name=title.name,
            )
            logger.info('Clearing title %s/%s for person_id=%r',
                        title.name_variant, title.name_language,
                        db_person.entity_id)

    def update_contact_info(self, db_person, hr_person):
        """Update person in Cerebrum with contact information"""
        hr_contacts = {
            self.co.ContactInfo(c.contact_type): (c.contact_value,
                                                  c.contact_pref)
            for c in hr_person.contact_infos}

        db_contacts = {
            self.co.ContactInfo(row['contact_type']): (row['contact_value'],
                                                       row['contact_pref'])
            for row in db_person.get_contact_info(source=self.source_system)}

        to_remove = set(db_contacts) - set(hr_contacts)
        to_add = set(hr_contacts) - set(db_contacts)
        to_update = set(ctype
                        for ctype in (set(hr_contacts) & set(db_contacts))
                        if hr_contacts[ctype] != db_contacts[ctype])

        for ctype in to_remove:
            db_value, db_pref = db_contacts[ctype]
            db_person.delete_contact_info(source=self.source_system,
                                          contact_type=ctype,
                                          pref=db_pref)
            logger.info('clearing contact %s (pref=%r) for person_id=%r',
                        ctype, db_pref, db_person.entity_id)

        for ctype in to_update:
            db_value, db_pref = db_contacts[ctype]
            hr_value, hr_pref = hr_contacts[ctype]
            db_person.add_contact_info(source=self.source_system, type=ctype,
                                       value=hr_value, pref=hr_pref)
            logger.info('updating contact %s (pref=%r/%r) for entity_id=%r',
                        ctype, db_pref, hr_pref, db_person.entity_id)

        for ctype in to_add:
            hr_value, hr_pref = hr_contacts[ctype]
            db_person.add_contact_info(source=self.source_system, type=ctype,
                                       value=hr_value, pref=hr_pref)
            logger.info('adding contact %s (pref=%r) for entity_id=%r',
                        ctype, hr_pref, db_person.entity_id)

    # TODO: should probaly be moved into sap_uio/dfo_sap subclasses
    def _get_ou_id(self, hr_ou_id):
        """Find id of ou in cerebrum from ou_id given by the hr system"""
        ou = Factory.get('OU')(self.database)
        ou.clear()
        if self.source_system == self.co.system_sap:
            ou.find_stedkode(
                hr_ou_id[0:2],
                hr_ou_id[2:4],
                hr_ou_id[4:6],
                cereconf.DEFAULT_INSTITUSJONSNR
            )
        else:
            ou.find_by_external_id(
                id_type=self.co.externalid_dfo_ou_id,
                external_id=hr_ou_id,
                source_system=self.source_system
            )
        return ou.entity_id

    def update_affiliations(self, db_person, hr_person):
        """Update person in Cerebrum with the latest affiliations"""
        hr_affiliations = set(
            models.HRAffiliation(
                ou_id=self._get_ou_id(aff.ou_id),
                affiliation=self.co.PersonAffiliation(aff.affiliation),
                status=self.co.PersonAffStatus(aff.affiliation, aff.status),
                precedence=aff.precedence)
            for aff in hr_person.affiliations
        )
        db_affiliations = set(
            models.HRAffiliation(
                    aff['ou_id'],
                    self.co.PersonAffiliation(aff['affiliation']),
                    self.co.PersonAffStatus(aff['status']),
                    precedence=aff['precedence'])
            for aff in db_person.list_affiliations(
                person_id=db_person.entity_id,
                source_system=self.source_system)
        )
        for aff in db_affiliations - hr_affiliations:
            db_person.delete_affiliation(
                ou_id=aff.ou_id,
                affiliation=aff.affiliation,
                source=self.source_system)
            logger.info('Removing affiliation %r on ou %r for id: %r',
                        unicode(aff.status),
                        aff.ou_id,
                        db_person.entity_id)
        for aff in hr_affiliations:
            db_person.add_affiliation(
                source_system=self.source_system,
                ou_id=aff.ou_id,
                affiliation=aff.affiliation,
                status=aff.status,
                precedence=aff.precedence
            )
            logger.info('Adding/updating affiliation %r on ou %r for id: %r',
                        unicode(aff.status),
                        aff.ou_id,
                        db_person.entity_id)
        db_person.write_db()
