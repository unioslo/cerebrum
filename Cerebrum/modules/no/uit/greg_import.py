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
from Cerebrum.modules.tasks import task_queue
from .greg_users import UitGregUserUpdateHandler

logger = logging.getLogger(__name__)


class _UitGregOrgunitIds(mapper.GregOrgunitIds):

    # Maps Ou identifiers in Greg (.roles[].orgunit.identifiers[])

    type_map = {
        # UiT doesn't use `Cerebrum.modules.orgreg`, for now...
        # # ('orgreg', 'orgreg_id'): 'ORGREG_OU_ID',
        ('sirk', 'legacy_stedkode'): 'NO_SKO',
    }


class _UitGregContactInfo(mapper.GregContactInfo):

    type_map = {
        'private_email': 'EMAIL',
        'private_mobile': 'PRIVATEMOBILE',
    }


class _UitGregPersonIds(mapper.GregPersonIds):

    type_map = {
        # We include the primary identifier from System-X.  This will help
        # match old Cerebrum/System-X guests with new Cerebrum/Greg guests.
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

    type_map = {
        # GF - Gjesteforsker
        'GF': 'MANUELL/gjesteforsker',

        # EM - Emeriti
        'EM': 'TILKNYTTET/emeritus',

        # EP - Ekstern Phd
        'EP': ('ANSATT/vitenskapelig', 'STUDENT/drgrad'),

        # IP - Innleid personell (vikar, "fast ansatt")
        'IP': 'ANSATT/tekadm',

        # OT - Oppdragstaker (konsulent, "timelønn/honorar")
        'OT': 'MANUELL/gjest',

        # EV - Eksamensvakt
        'EV': 'MANUELL/gjest',

        # ES - Ekstern SRU (styre, råd, utvalg)
        'ES': 'MANUELL/gjest',

        # ST - Student
        'ST': 'STUDENT/aktiv',

        # LB - Leieboer
        'LB': 'MANUELL/gjest',

        # XS - Ekstern sensor
        'XS': 'MANUELL/gjest',
    }

    get_orgunit_ids = _UitGregOrgunitIds()


class _UitGregSpreads(mapper.GregRoles):
    """
    Get personal spreads from roles.

    We (ab)use the GregRoles mapper in order to map/filter spreads from roles.
    This mapper will yield tuples of:

        (spread, empty ou-id tuple, start date, end date)
    """
    type_map = {
        'GF': ('CIM_person',),
        'EM': ('CIM_person',),
        'EP': ('CIM_person',),
        'IP': ('CIM_person',),
        # 'OT': (),
        # 'EV': (),
        # 'ES': (),
        # 'ST': (),
        'LB': ('CIM_person',),
        # 'XS': (),
    }

    def get_orgunit_ids(self, orgunit):
        # mock generator - never yields any results
        if False:
            yield (None, None)


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

    def _trigger_user_update(self, greg_person, person_obj, _today=None):
        """
        Queue a user update for the given person.
        """
        greg_id = greg_person.get('id')
        person_id = int(person_obj.entity_id)

        # We calculate a suitable expire-date for the person, based on the
        # current Greg roles.
        affs = list(self.mapper.get_affiliations(greg_person))
        expire_date = calculate_expire_date(affs, _today=_today)
        logger.debug("Person id=%r (greg-id=%r): account should expire at=%r",
                     person_id, greg_id, expire_date)

        task = UitGregUserUpdateHandler.create_task(person_id,
                                                    expire_date=expire_date)
        qdb = task_queue.TaskQueue(self.db)
        qdb.push_task(task)

    def _sync_person_spreads(self, greg_person, person_obj, _today=None):
        """ Sync person spreads from Greg data. """
        today = _today or datetime.date.today()
        greg_spreads = {}
        get_spreads = _UitGregSpreads()

        # Collect spreads and a potential expire-date (in case we want to use
        # spread_expire for these)
        for s, _, _, end_date in get_spreads(greg_person,
                                             filter_active_at=today):
            spread = self.const.get_constant(self.const.Spread, s)
            if spread not in greg_spreads or greg_spreads[spread] < end_date:
                greg_spreads[spread] = end_date

        logger.debug("person id=%r should have spreads %s",
                     person_obj.entity_id, repr(list(greg_spreads)))

        # NOTE: The CIM-spread is handled by the PAGA/employee import which
        # will add/remove this spread.  There is a risk that spreads added by
        # this method will get removed by the PAGA import.
        #
        # It's not really possible to decide if a person should have the
        # CIM-spread without looking at information from *both* PAGA and Greg
        # at the same time.
        #
        # Spread expire would be the obvious solution, but it doesn't currently
        # work with personal spreads (only account spreads).  UiT wants us to
        # *add* the spread if it looks like the user needs it, but never remove
        # them...
        current_spreads = set(
            self.const.get_constant(self.const.Spread, row['spread'])
            for row in person_obj.get_spread())
        for spread in (set(greg_spreads) - current_spreads):
            person_obj.add_spread(spread)

    def remove(self, greg_person, person_obj):
        changes = super(UitGregImporter, self).remove(greg_person, person_obj)
        self._trigger_user_update(greg_person, person_obj)
        return changes

    def update(self, greg_person, person_obj, _today=None):
        changes = super(UitGregImporter, self).update(greg_person, person_obj,
                                                      _today=_today)
        self._sync_person_spreads(greg_person, person_obj, _today=_today)
        self._trigger_user_update(greg_person, person_obj, _today=_today)
        return changes
