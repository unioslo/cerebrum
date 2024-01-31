# -*- coding: utf-8 -*-
#
# Copyright 2021-2023 University of Oslo, Norway
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
Greg person import/update.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging
import datetime

import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.modules.import_utils.groups import GroupMembershipSetter
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
from Cerebrum.utils.module import resolve

from .datasource import GregDatasource
from .mapper import GregMapper

logger = logging.getLogger(__name__)


def get_import_class(cereconf=cereconf):
    """
    Get preferred import class from config module/object *cereconf*.

    TODO: Or should we re-factor the greg client config into a full greg
    config, with import class and everything?
    """
    import_spec = getattr(cereconf, 'GREG_IMPORT', None)
    if import_spec:
        cls = resolve(import_spec)
    else:
        cls = GregImporter
    logger.info("greg import class=%s", repr(cls))
    return cls


def _is_deceased(person_obj, _today=None):
    """ helper - check if a Person object is deceased. """
    today = _today or datetime.date.today()
    return (
        person_obj
        and person_obj.deceased_date
        and date_compat.get_date(person_obj.deceased_date) < today)


class GregImporter(object):

    REQUIRED_PERSON_ID = (
        'NO_BIRTHNO',
        'PASSNR',
    )

    MATCH_ID_TYPES = (
        'GREG_PID',
    )

    # Map consent name to `Cerebrum.group.template.GroupTemplate`
    CONSENT_GROUPS = {}

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

    def _sync_consent_groups(self, person_obj, consents):
        """
        Sync consents from greg to personal group memberships in Cerebrum.

        :type person_obj: Cerebrum.Person.Person
        :param consents: collection of (mapped) consent values for this person

        :returns tuple:
            Returns a pair of tuples -- added to groups, removed from groups
        """
        added = []
        removed = []

        for consent, group_template in self.CONSENT_GROUPS.items():
            is_consent = consent in consents
            group_name = group_template.group_name
            update_group = GroupMembershipSetter(group_template)
            if update_group(self.db, person_obj.entity_id, is_consent):
                if is_consent:
                    added.append(group_name)
                else:
                    removed.append(group_name)

        return (tuple(added), tuple(removed))

    def get_person(self, greg_person):
        """ Find matching person from a Greg person dict. """
        search = PersonMatcher(self.MATCH_ID_TYPES)
        criterias = tuple(self.mapper.get_person_ids(greg_person))
        if not criterias:
            raise ValueError('invalid person: no external_ids')
        return search(self.db, criterias, required=False)

    def get_ou(self, orgunit_ids):
        """ Find matching ou from a Greg orgunit dict. """
        search = OuMatcher()
        criterias = tuple((id_type, id_value)
                          for id_type, id_value in orgunit_ids)
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

        is_deceased = _is_deceased(person_obj)
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

        changes = self.update(greg_person, person_obj)
        return person_obj, changes

    def remove(self, greg_person, person_obj):
        """ Clear greg data from a Person object.  """
        if person_obj is None or not person_obj.entity_id:
            raise ValueError('remove() called without cerebrum person!')

        changes = {}
        changes['person-name'] = self._sync_name(person_obj, ())

        # Note; We need to continue updating external ids - as this will allow
        # us to cross-reference persons *created* by greg with persons that may
        # appear in other source systems.
        #
        greg_ids = tuple(self.mapper.get_person_ids(greg_person))
        changes['external-id'] = self._sync_ids(person_obj, greg_ids)

        changes['contact-info'] = self._sync_cinfo(person_obj, ())
        changes['affiliation'] = self._sync_affs(person_obj, ())
        changes['consent-group'] = self._sync_consent_groups(person_obj, ())

        return changes

    def update(self, greg_person, person_obj, _today=None):
        """ Update the Person object using employee_data.  """
        if not greg_person:
            raise ValueError('update() called without greg person data!')
        if person_obj is None or not person_obj.entity_id:
            raise ValueError('update() called without cerebrum person!')

        today = _today or datetime.date.today()

        changes = {}

        # 'person-name' -> added, updated, removed
        greg_names = tuple(self.mapper.get_names(greg_person))
        changes['person-name'] = self._sync_name(person_obj, greg_names)

        # 'external-id' -> added, updated, removed
        greg_ids = tuple(self.mapper.get_person_ids(greg_person))
        changes['external-id'] = self._sync_ids(person_obj, greg_ids)

        # 'contact-info' -> added, updated, removed
        greg_cinfo = tuple(self.mapper.get_contact_info(greg_person))
        changes['contact-info'] = self._sync_cinfo(person_obj, greg_cinfo)

        # 'affiliation' -> added, kept, removed
        affs = tuple(
            (aff_status, self.get_ou(org_ids).entity_id)
            for aff_status, org_ids, start_date, end_date
            in self.mapper.get_affiliations(greg_person,
                                            filter_active_at=today)
        )
        changes['affiliation'] = self._sync_affs(person_obj, affs)

        # 'consent-group' -> added, removed
        consents = tuple(self.mapper.get_consents(greg_person))
        changes['consent-group'] = self._sync_consent_groups(person_obj,
                                                             consents)

        return changes
