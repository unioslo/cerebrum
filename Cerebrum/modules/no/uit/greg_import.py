# -*- coding: utf-8 -*-
#
# Copyright 2023 University of Oslo, Norway
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
UiT-specific Greg import logic.
"""
import datetime
import logging

from Cerebrum.modules.greg import mapper
from Cerebrum.modules.greg import importer
# from Cerebrum.modules.tasks import task_queue
# from .greg_users import UitGregUserUpdateHandler

logger = logging.getLogger(__name__)


class _UitGregOrgunitIds(mapper.GregOrgunitIds):

    # Maps Ou identifiers in Greg (.roles[].orgunit.identifiers[])
    #
    # TODO: Which identifiers will exist at UiT?
    #
    # For now, we'll be able to test import of a single person by adding valid
    # GREG_OU_ID values on relevant org units in Cerebrum...

    type_map = {
        # TODO: It looks like UiT will have a orgreg/orgreg-id which is useful
        # if we ever move the OU import for UiT over to Orgreg.  For now
        # though, UiT doesn't use `Cerebrum.modules.orgreg`, and thus don't
        # have this id-type.
        # ('orgreg', 'orgreg_id'): 'ORGREG_OU_ID',

        # TODO: We should probably have a location code, but what will this be
        # named in greg-uit-*?  Probably 'legacy_stedkode', but from which
        # source system?
        # ('orgreg', 'legacy_stedkode'): 'NO_SKO',
    }


class _UitGregContactInfo(mapper.GregContactInfo):

    type_map = {
        'private_mobile': 'PRIVATEMOBILE',
        'private_email': 'EMAIL',
    }


class _UitGregPersonIds(mapper.GregPersonIds):

    type_map = {
        # We include the primary identifier from System-X.
        # This will help match old Cerebrum/System-X guests with new
        # Cerebrum/Greg entries.
        ('system-x', 'migration_id'): 'SYS_X_ID',

        'norwegian_national_id_number': 'NO_BIRTHNO',
        'passport_number': 'PASSNR',
    }


class _UitGregConsents(mapper.GregConsents):

    # TODO: Will UiT have consents? If so, Which consents do we need to
    # consider?
    #
    # Looks like they have a "UiTs_ICT_regulation_valid_from_15-10-22-ENG"
    # in the greg-uit-test system.   Should this be used?  If so, it sounds
    # like a consent that should maybe be checked in the
    # _UitGregMapper.is_active() call?

    type_map = {}


class _UitGregRoles(mapper.GregRoles):

    # TODO: What roles will UiT have?
    #
    # These roles are the default greg-uio-* roles, which seems to be the only
    # ones registered in greg-uit-test.  We've matched them with some valid
    # affs for now, just for testing purposes.  This mapping *must* be updated
    # with real roles and proper affs.

    type_map = {
        'emeritus': 'TILKNYTTET/emeritus',
        'external-consultant': 'MANUELL/gjest',
        'external-partner': 'MANUELL/gjest',
        'guest-researcher': 'TILKNYTTET/fagperson',
    }

    get_orgunit_ids = _UitGregOrgunitIds()


class _UitGregMapper(mapper.GregMapper):

    get_contact_info = _UitGregContactInfo()
    get_person_ids = _UitGregPersonIds()
    get_affiliations = _UitGregRoles()
    get_consents = _UitGregConsents()

    # get_names  # inherited
    # is_active  # inherited - uses get_affiliations


def calculate_expire_date(affiliation_data, _today=None):
    """
    Extract a suitable *expire-date* from affiliation data.

    :param affiliation_data: output from :class:`._UitGregRoles`
    :param _today: calculate for a specific date
    """
    today = _today or datetime.date.today()
    expire_date = None

    for _, _, start_date, end_date in affiliation_data:
        if start_date > today:
            # Not started, so not really relevant yet.  We'll get a new message
            # once this aff "activates"...
            continue

        # Find the lastest end-date of any aff that has started
        if not expire_date or end_date > expire_date:
            expire_date = end_date

    if expire_date:
        return expire_date
    else:
        return None


class UitGregImporter(importer.GregImporter):
    """
    Custom importer for UiT.

    Changes from superclass:

    1. Custom mapper
    2. Add a user update task whenever a person is processed.
    """

    REQUIRED_PERSON_ID = (
        'NO_BIRTHNO',
        'PASSNR',
    )

    MATCH_ID_TYPES = (
        'GREG_PID',
    )

    CONSENT_GROUPS = {}

    mapper = _UitGregMapper()

    def _trigger_user_update(self, greg_person, person_obj):
        """ Queue a user update for the given person. """
        greg_id = greg_person.get('id')
        person_id = person_obj.entity_id

        affs = list(self.mapper.get_affiliations(greg_person))

        # We need to embed a potential expire_date to extend the current
        # expire_date when creating/reviving/updating users at UiT.
        #
        # If no expire_date can be found in affs, we won't prolong the
        # expire_date of any account in the user update...
        expire_date = calculate_expire_date(affs)
        logger.debug("Person id=%r (greg-id=%r): account should expire at=%r",
                     person_id, greg_id, expire_date)
        # TODO: Create and push task when the greg_users module is ready...
        #
        # task = UitGregUserUpdateHandler.new_task(int(person_obj.entity_id),
        #                                          expire_date=expire_date)
        # qdb = task_queue.TaskQueue(self.db)
        # qdb.push_task(task)

    def remove(self, greg_person, person_obj):
        changes = super(UitGregImporter, self).remove(greg_person, person_obj)
        self._trigger_user_update(greg_person, person_obj)
        return changes

    def update(self, greg_person, person_obj):
        changes = super(UitGregImporter, self).update(greg_person, person_obj)
        self._trigger_user_update(greg_person, person_obj)
        return changes
