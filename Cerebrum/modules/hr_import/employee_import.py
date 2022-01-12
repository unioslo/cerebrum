# -*- coding: utf-8 -*-
#
# Copyright 2020-2021 University of Oslo, Norway
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
from Cerebrum.utils.date_compat import get_date
from Cerebrum.modules.hr_import.errors import NonExistentOuError
from Cerebrum.modules.import_utils.matcher import OuMatcher
from Cerebrum.modules.import_utils.syncs import (
    AffiliationSync,
    ContactInfoSync,
    ExternalIdSync,
    NameLanguageSync,
    PersonNameSync,
)

from .importer import AbstractImport
from . import models

logger = logging.getLogger(__name__)


class EmployeeImportBase(AbstractImport):

    REQUIRED_PERSON_ID = ('NO_BIRTHNO', 'PASSNR')

    def __init__(self, *args, **kwargs):
        super(EmployeeImportBase, self).__init__(*args, **kwargs)
        self.updater = HRDataImport(self.db, self.source_system)

    @property
    def const(self):
        """ Constants. """
        if not hasattr(self, '_const'):
            self._const = Factory.get('Constants')(self.db)
        return self._const

    def create(self, employee_data):
        """ Create a new Person object using employee_data. """
        logger.debug('create(%r)', employee_data)
        if employee_data is None:
            raise ValueError('create() called without hr data!')

        if not any(i.id_type in self.REQUIRED_PERSON_ID
                   for i in employee_data.external_ids):
            raise ValueError('None of required id types %s present: %s' %
                             (self.REQUIRED_PERSON_ID,
                              employee_data.external_ids))

        person_obj = Factory.get('Person')(self.db)
        # TODO: Search for soft matches (names) and warn?
        gender = self.const.Gender(employee_data.gender)
        if employee_data.birth_date is None:
            raise ValueError('No birth date, unable to create!')
        person_obj.populate(employee_data.birth_date, gender)
        person_obj.write_db()
        if not person_obj.entity_id:
            raise RuntimeError('Write failed, unable to create!')

        logger.info('created new person, id=%r, person=%r',
                    person_obj.entity_id, employee_data)
        self.update(employee_data, person_obj)

    def update(self, employee_data, person_obj):
        """ Update the Person object using employee_data. """
        if employee_data is None:
            raise ValueError('update() called without hr data!')
        if person_obj is None or not person_obj.entity_id:
            raise ValueError('update() called without cerebrum person!')
        self.updater.update_person(person_obj, employee_data)

    def remove(self, hr_object, db_object):
        """ Clear HR data from a Person object. """
        if db_object is None or not db_object.entity_id:
            raise ValueError('remove() called without cerebrum person!')
        self.updater.remove_person(db_object, hr_object)


# TODO:
#  Would it not be simpler if the functionality of this class was part of
#  ``EmployeeImportBase`` ?
#  We want to move ``get_ou`` into separate subclasses, but it feels like
#  unnecessary complexity to have separate subclasses of both
#  ``EmployeeImportBase`` and ``HRDataImport`` ?
class HRDataImport(object):

    def __init__(self, database, source_system):
        """
        :param database:
        :param source_system:
        """
        self.database = db = database
        self.source_system = source_system
        self.co = co = Factory.get('Constants')(db)

        self._sync_affs = AffiliationSync(db, source_system)
        self._sync_cinfo = ContactInfoSync(db, source_system)
        self._sync_ids = ExternalIdSync(db, source_system)
        self._sync_name = PersonNameSync(db, source_system,
                                         (co.name_first, co.name_last))
        self._sync_titles = NameLanguageSync(db, (co.work_title,
                                                  co.personal_title))

    def remove_person(self, db_person, hr_person):
        logger.debug('remove_person(%r, %r)',
                     db_person.entity_id, hr_person)

        source2id_type = {
            self.co.system_sap: 'NO_SAPNO',
            self.co.system_dfo_sap: 'DFO_PID',
        }

        # The strategy for removing persons is to create an empty HRPerson
        # containing only the hr_id, and then calling the update methods.
        empty_hr_person = models.HRPerson(
            hr_id=hr_person.hr_id,
            first_name=None,
            last_name=None,
            # birth_date and gender is not needed unless self.update_basic()
            # is called
            birth_date=None,
            gender=None,
        )

        keep_id_type = source2id_type[self.source_system]
        empty_hr_person.external_ids = set(
            id_ for id_ in hr_person.external_ids if
            id_.id_type == keep_id_type
        )

        # Call every update method except self.update_basic()
        self.update_external_ids(db_person, empty_hr_person)
        self.update_names(db_person, empty_hr_person)
        # TODO: temporary - disable work title update
        self.update_titles(db_person, empty_hr_person)
        self.update_contact_info(db_person, empty_hr_person)
        self.update_affiliations(db_person, empty_hr_person)
        logger.info('removed person id=%r', db_person.entity_id)

    def update_person(self, db_person, hr_person):
        """Call all the update functions, creating or updating a person"""
        logger.debug('update_person(%r, %r)',
                     db_person.entity_id, hr_person)
        self.update_basic(db_person, hr_person)
        self.update_external_ids(db_person, hr_person)
        self.update_names(db_person, hr_person)
        self.update_titles(db_person, hr_person)
        self.update_contact_info(db_person, hr_person)
        self.update_affiliations(db_person, hr_person)
        logger.info('updated person id=%r', db_person.entity_id)

    def update_basic(self, db_person, hr_person):
        """Update person with birth date and gender"""
        logger.debug('update_basic(%r, %r)', db_person.entity_id, hr_person)
        if hr_person.gender:
            gender = self.co.Gender(hr_person.gender)
        else:
            gender = self.co.gender_unknown

        change = False

        if db_person.gender != gender:
            logger.info('basic_info: updating gender, id=%r',
                        db_person.entity_id)
            db_person.gender = gender
            change = True

        if hr_person.birth_date is None:
            logger.warning(
                'basic_info: missing birth date, id=%r, person=%r)',
                db_person.entity_id, hr_person)
        elif get_date(db_person.birth_date) != hr_person.birth_date:
            logger.info('basic_info: updating birth_date, id=%r',
                        db_person.entity_id)
            db_person.birth_date = hr_person.birth_date
            change = True

        if change:
            db_person.write_db()
        else:
            logger.info('basic_info: no changes, id=%r',
                        db_person.entity_id)

    def update_external_ids(self, db_person, hr_person):
        """Update person in Cerebrum with appropriate external ids"""
        hr_ids = tuple((i.id_type, i.external_id)
                       for i in hr_person.external_ids)
        self._sync_ids(db_person, hr_ids)

    def update_names(self, db_person, hr_person):
        names = tuple(
            (name_type, name)
            for name_type, name in (('FIRST', hr_person.first_name),
                                    ('LAST', hr_person.last_name))
            if name and name.strip())
        self._sync_name(db_person, names)

    def update_titles(self, db_person, hr_person):
        hr_titles = tuple(
            (t.name_variant, t.name_language, t.name)
            for t in hr_person.titles)
        self._sync_titles(db_person, hr_titles)

    def update_contact_info(self, db_person, hr_person):
        """Update person in Cerebrum with contact information"""
        hr_contacts = tuple((c.contact_type, c.contact_value)
                            for c in hr_person.contact_infos)
        self._sync_cinfo(db_person, hr_contacts)

    def get_ou(self, ident):
        """ Find matching ou from a Greg orgunit dict. """
        ou = Factory.get('OU')(self.database)
        if isinstance(ident, int):
            ident = str(ident)

        # TODO: Remove this (and the ..no.uio.sap import)
        if self.source_system == self.co.system_sap:
            try:
                ou.find_sko(ident)
                return ou
            except Errors.NotFoundError:
                raise NonExistentOuError("Invalid stedkode: " + repr(ident))

        search = OuMatcher()
        criterias = [('DFO_OU_ID', ident)]
        try:
            return search(self.database, criterias, required=True)
        except Errors.NotFoundError:
            raise NonExistentOuError("Invalid OU: " + repr(criterias))

    def update_affiliations(self, db_person, hr_person):
        """Update person in Cerebrum with the latest affiliations"""
        aff_tuples = []
        for aff in hr_person.affiliations:
            affstr = aff.affiliation + '/' + aff.status
            ou = self.get_ou(aff.ou_id)
            ou_id = ou.entity_id
            aff_data = (affstr, ou_id)
            aff_tuples.append(aff_data)
        self._sync_affs(db_person, aff_tuples)
