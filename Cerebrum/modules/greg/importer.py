# -*- coding: utf-8 -*-
#
# Copyright 2021 University of Oslo, Norway
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
""" Greg person import/update.  """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging
import datetime

from Cerebrum.Utils import Factory
from Cerebrum.modules.import_utils.matcher import (
    OuMatcher,
    PersonMatcher,
)
from Cerebrum.modules.import_utils.syncs import (
    AffiliationSync,
    ContactInfoSync,
    ExternalIdSync,
    PersonNameSync,
)
from Cerebrum.utils import date_compat

from .consent import sync_greg_consent
from .datasource import GregDatasource
from .mapper import GregMapper

logger = logging.getLogger(__name__)


class GregImporter(object):

    REQUIRED_PERSON_ID = (
        'NO_BIRTHNO',
        'PASSNR',
    )

    MATCH_ID_TYPES = (
        'GREG_PID',
    )

    CONSENT_GROUPS = {
        'greg-publish': sync_greg_consent,
    }

    mapper = GregMapper()

    def __init__(self, db, client):
        self.db = db
        self.const = co = Factory.get('Constants')(db)
        self.datasource = GregDatasource(client)

        source_system = co.system_greg
        self._sync_affs = AffiliationSync(db, source_system)
        self._sync_cinfo = ContactInfoSync(db, source_system)
        self._sync_ids = ExternalIdSync(db, source_system)
        self._sync_name = PersonNameSync(db, source_system, (co.name_first,
                                                             co.name_last))

    def _sync_consents(self, person_obj, consents):
        """ Sync consents from greg. """
        # Consents represented as groups:
        for consent, update_group in self.CONSENT_GROUPS.items():
            is_consent = consent in consents
            update_group(self.db, person_obj.entity_id, is_consent)
        # TODO: Also sync to Cerebrum.modules.consent?

    def get_person(self, greg_person):
        """ Find matching person from a Greg person dict. """
        search = PersonMatcher(self.MATCH_ID_TYPES)
        criterias = tuple(self.mapper.get_person_ids(greg_person))
        if not criterias:
            raise ValueError('invalid person: no external_ids')
        return search(self.db, criterias, required=False)

    def get_ou(self, greg_orgunit):
        """ Find matching ou from a Greg orgunit dict. """
        search = OuMatcher()
        criterias = tuple(self.mapper.get_orgunit_ids(greg_orgunit))
        if not criterias:
            raise ValueError('invalid orgunit: no external_ids')
        return search(self.db, criterias, required=True)

    def handle_reference(self, reference):
        """
        Initiate hr import from reference.

        This is the entrypoint for use with e.g. scripts.
        Fetches object data from the datasource and calls handle_object.
        """
        greg_person = self.datasource.get_object(reference)
        db_object = self.get_person(greg_person)
        return self.handle_object(greg_person, db_object)

    def handle_object(self, greg_person, person_obj):
        """
        Process info from Greg and update Cerebrum (i.e. initiate import).

        This method inspects and compares source data and cerebrum data, and
        calls the relevant create/update/remove method.

        :type greg_person: dict
        :type person_obj: Cerebrum.Person.Person, NoneType
        """
        greg_id = greg_person['id']

        is_deceased = (
            person_obj
            and person_obj.deceased_date
            and (date_compat.get_date(person_obj.deceased_date)
                 < datetime.date.today()))
        if is_deceased:
            logger.warning('person_id=%s is marked as deceased',
                           person_obj.entity_id)

        if self.mapper.is_active(greg_person) and not is_deceased:
            if person_obj:
                logger.info('handle_object: update greg_id=%s, person_id=%s',
                            greg_id, person_obj.entity_id)
                self.update(greg_person, person_obj)
            else:
                logger.info('handle_object: creating greg_id=%s', greg_id)
                self.create(greg_person)
        elif person_obj:
            logger.info('handle_object: remove greg_id=%s, person_id=%s',
                        greg_id, person_obj.entity_id)
            self.remove(greg_person, person_obj)
        else:
            logger.info('handle_object: ignoring greg_id=%s', greg_id)

        # Greg sends new messages for future events, no retry dates needed
        return tuple()

    def create(self, greg_person):
        """ Create a new Person object using greg person data. """
        if not greg_person:
            raise ValueError('create() called without greg data!')
        greg_id = greg_person['id']

        id_types = set(id_type for id_type, _
                       in self.mapper.get_person_ids(greg_person))

        if (self.REQUIRED_PERSON_ID
                and not any(id_type in self.REQUIRED_PERSON_ID
                            for id_type in id_types)):
            raise ValueError('Missing required identifier, need one of '
                             + repr(self.REQUIRED_PERSON_ID))

        person_obj = Factory.get('Person')(self.db)
        gender = self.const.gender_unknown
        dob = greg_person['date_of_birth']
        if not dob:
            raise ValueError('No birth date, unable to create!')
        person_obj.populate(dob, gender)
        person_obj.write_db()

        if not person_obj.entity_id:
            raise RuntimeError('Write failed, unable to create!')

        logger.info('created new person, greg_id=%s, person_id=%s',
                    greg_id, person_obj.entity_id)
        self.update(greg_person, person_obj)

    def remove(self, greg_person, person_obj):
        """ Clear HR data from a Person object. """
        if person_obj is None or not person_obj.entity_id:
            raise ValueError('remove() called without cerebrum person!')

        # TODO/TBD: Are there any steps needed besides clearing everything
        # (except the GREG_PID) that update() sets?
        blank_person = {'id': greg_person['id']}
        self.update(blank_person, person_obj)

    def update(self, greg_person, person_obj):
        """ Update the Person object using employee_data. """
        if not greg_person:
            raise ValueError('update() called without greg person data!')
        if person_obj is None or not person_obj.entity_id:
            raise ValueError('update() called without cerebrum person!')

        self._sync_name(person_obj, self.mapper.get_names(greg_person))
        self._sync_ids(person_obj, self.mapper.get_person_ids(greg_person))
        self._sync_cinfo(person_obj, self.mapper.get_contact_info(greg_person))
        affs = (
            (aff_status, self.get_ou(ou_data).entity_id)
            for aff_status, ou_data
            in self.mapper.get_affiliations(greg_person)
        )
        self._sync_affs(person_obj, affs)
        self._sync_consents(person_obj, self.mapper.get_consents(greg_person))
