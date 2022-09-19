# -*- coding: utf-8 -*-
#
# Copyright 2020-2022 University of Oslo, Norway
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
import datetime
import logging

from Cerebrum.Utils import Factory
from Cerebrum.utils.date_compat import get_date
from Cerebrum.modules.hr_import.errors import NonExistentOuError
from Cerebrum.modules.hr_import.mapper import HrPerson
from Cerebrum.modules.import_utils.matcher import OuMatcher
from Cerebrum.modules.import_utils.syncs import (
    AffiliationSync,
    ContactInfoSync,
    ExternalIdSync,
    NameLanguageSync,
    PersonNameSync,
)

from .importer import AbstractImport

logger = logging.getLogger(__name__)

# extra loggger for debugging values - can be turned on by logger config
# TODO: This should probably be a feature in the import utils
debug_log = logger.getChild('debug')
debug_log.propagate = False
debug_log.addHandler(logging.NullHandler())


class EmployeeImportBase(AbstractImport):

    # To create a new person, at least one of these external-ids must be
    # present in the given `hr_object.ids`.
    REQUIRED_PERSON_ID = ('NO_BIRTHNO', 'PASSNR')

    # When removing a person, keep any external-ids of these types for later
    # imports/cross-references with other systems.
    KEEP_ID_TYPES = ('NO_BIRTHNO', 'PASSNR')

    def __init__(self, *args, **kwargs):
        super(EmployeeImportBase, self).__init__(*args, **kwargs)

        self._sync_affs = AffiliationSync(self.db, self.source_system)
        self._sync_cinfo = ContactInfoSync(self.db, self.source_system)
        self._sync_ids = ExternalIdSync(self.db, self.source_system)
        self._sync_name = PersonNameSync(self.db, self.source_system,
                                         (self.const.name_first,
                                          self.const.name_last))
        self._sync_titles = NameLanguageSync(self.db,
                                             (self.const.work_title,
                                              self.const.personal_title))

    @property
    def const(self):
        """ Constants. """
        if not hasattr(self, '_const'):
            self._const = Factory.get('Constants')(self.db)
        return self._const

    def create(self, hr_object):
        """ Create a new Person object using hr_object. """
        logger.debug('create(%r)', hr_object)
        if hr_object is None:
            raise ValueError('create() called without hr data!')

        id_types = [id_type for id_type, _ in hr_object.ids]
        if not any(id_type in self.REQUIRED_PERSON_ID
                   for id_type in id_types):
            raise ValueError('None of required id types %s present: %s'
                             % (self.REQUIRED_PERSON_ID, id_types))

        db_object = Factory.get('Person')(self.db)

        # TODO: Search for soft matches (names) and warn?

        gender = self.const.Gender(hr_object.gender)
        if hr_object.birth_date is None:
            raise ValueError('No birth date, unable to create!')
        db_object.populate(hr_object.birth_date, gender)
        db_object.write_db()
        if not db_object.entity_id:
            raise RuntimeError('Write failed, unable to create!')

        logger.info('created new person with id=%r from=%r',
                    db_object.entity_id, hr_object)
        self.update(hr_object, db_object)

    def update(self, hr_object, db_object):
        """ Update the Person object using hr_object. """
        logger.debug('update(%r, %r)', hr_object, db_object.entity_id)
        if hr_object is None:
            raise ValueError('update() called without hr data!')
        if db_object is None or not db_object.entity_id:
            raise ValueError('update() called without cerebrum person!')

        self._update_basic(db_object, hr_object)
        self._update_external_ids(db_object, hr_object)
        self._update_names(db_object, hr_object)
        self._update_titles(db_object, hr_object)
        self._update_contact_info(db_object, hr_object)
        self._update_affiliations(db_object, hr_object)
        logger.info('updated person id=%r from=%r',
                    db_object.entity_id, hr_object)

    def remove(self, hr_object, db_object):
        """ Clear HR data from a Person object. """
        logger.debug('remove(%r, %r)', hr_object, db_object.entity_id)
        if db_object is None or not db_object.entity_id:
            raise ValueError('remove() called without cerebrum person!')

        # The strategy for removing persons is to create an empty HRPerson
        # containing only the hr_id, and then calling the update methods.
        empty_person = HrPerson(
            hr_id=hr_object.hr_id,
            birth_date=hr_object.birth_date,
            gender=hr_object.gender,
            enable=hr_object.enable,
        )

        # Add any external-id that we want to keep
        empty_person.ids = [
            (id_type, id_value)
            for id_type, id_value in hr_object.ids
            if id_type in self.KEEP_ID_TYPES]

        # Call every update method except self._update_basic()
        self._update_external_ids(db_object, empty_person)
        self._update_names(db_object, empty_person)
        self._update_titles(db_object, empty_person)
        self._update_contact_info(db_object, empty_person)
        self._update_affiliations(db_object, empty_person)
        logger.info('removed person id=%r from=%r',
                    db_object.entity_id, hr_object)

    def _update_basic(self, db_person, hr_person):
        """Update person with birth date and gender"""
        debug_log.debug('basic-info: id=%r, birth_date=%r, gender=%r',
                        hr_person.hr_id, hr_person.birth_date,
                        hr_person.gender)
        change = False

        # TODO: We should probably not update these fields - if there is a
        # conflict with another source system, we should simply keep whatever
        # is already in Cerebrum.

        gender = self.const.Gender(hr_person.gender)
        if db_person.gender != gender:
            logger.info('basic-info: updating gender, id=%r',
                        db_person.entity_id)
            db_person.gender = gender
            change = True

        if hr_person.birth_date is None:
            logger.warning(
                'basic-info: missing birth date for id=%r, hr_object=%r)',
                db_person.entity_id, hr_person)
        elif get_date(db_person.birth_date) != hr_person.birth_date:
            logger.info('basic-info: updating birth_date, id=%r',
                        db_person.entity_id)
            db_person.birth_date = hr_person.birth_date
            change = True

        if change:
            db_person.write_db()
        else:
            logger.info('basic-info: no changes, id=%r',
                        db_person.entity_id)

    def _update_external_ids(self, db_person, hr_person):
        """Update person in Cerebrum with appropriate external ids"""
        debug_log.debug('external-id: %s', repr(hr_person.ids))
        self._sync_ids(db_person, hr_person.ids)

    def _update_names(self, db_person, hr_person):
        debug_log.debug('names: %s', repr(hr_person.names))
        self._sync_name(db_person, hr_person.names)

    def _update_titles(self, db_person, hr_person):
        debug_log.debug('titles: %s', repr(hr_person.titles))
        self._sync_titles(db_person, hr_person.titles)

    def _update_contact_info(self, db_person, hr_person):
        """Update person in Cerebrum with contact information"""
        debug_log.debug('contact-info: %s', repr(hr_person.contacts))
        self._sync_cinfo(db_person, hr_person.contacts)

    def _get_ou(self, criterias):
        """ Find matching ou from a Greg orgunit dict. """
        search = OuMatcher()
        if not criterias:
            raise ValueError('invalid orgunit: no ids')
        return search(self.db, criterias, required=True)

    def _update_affiliations(self, db_person, hr_person, _today=None):
        """Update person in Cerebrum with the latest affiliations"""
        debug_log.debug('affiliations: %s', repr(hr_person.affiliations))
        today = _today or datetime.date.today()
        aff_tuples = []
        for aff, ou_idents, start, end in hr_person.affiliations:
            # TODO: Apply grace here?
            if start and start > today or end and end < today:
                continue
            ou = self._get_ou(ou_idents)
            if not ou:
                raise NonExistentOuError("invalid ou: " + repr(ou_idents))
            aff_data = (aff, ou.entity_id)
            aff_tuples.append(aff_data)
        self._sync_affs(db_person, aff_tuples)
