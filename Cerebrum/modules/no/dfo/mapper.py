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
Mapper for DFØ-SAP.

Input data structure
--------------------
The employee_data object should follow the format returned by
py:func:`.datasource.parse_employee`, supplemented by a assignments dict with
assignments data from py:func:`.datasource.parse_assignment`.

py:func:`.datasource.prepare_employee_data` can be used to construct this data
structure from raw DFØ employee/assignment data.

::

    {
        'id': <normalized employee id>,
        '…': <normalized person fields…>,
        'assignments': {
            <assignment-id>: {<normalized assignment-data…>},
            …
        }
    }


Future changes
--------------
These mappers are curerntly not configurable.  We might want to implement:

- An init for each individual mapper type with options, custom mappings.
- Init + Config for the py:class:`.EmployeeMapper` to configure individual
  mapper behavior.

The alternative is to subclass and build custom mappers for custom behavior.
"""
from __future__ import unicode_literals

import re
import collections
import datetime
import logging

from Cerebrum.modules.hr_import.mapper import AbstractMapper, HrPerson
from Cerebrum.modules.no.dfo import title_maps
from Cerebrum.utils import phone as phone_utils
from Cerebrum.utils.sorting import make_priority_lookup


logger = logging.getLogger(__name__)


class DfoPersonIds(object):
    """
    Extract external ids from dfo employee data.

    >>> get_ids = DfoPersonIds()
    >>> list(get_ids({
    ...     'id': '01234567',
    ...     'fnr': '17912099997',
    ...     'annenId': [{'idType': '02', 'idLand': 'NO', 'idNr': '123'}]}))
    [('DFO_PID', '01234567'),
     ('NO_BIRTHNO', '17912099997'),
     ('PASSNR', 'NO-123')]
    """

    # Ignore certain invalid (dummy) birthno/nin patterns
    ignore_nin_pattern = re.compile(r'.+00[012]00$')

    def _normalize_nin(self, value):
        """ Validate and normalize NIN. """
        # NOTE: We may want to validate nin/fnr better (checksums etc...)
        if value and not self.ignore_nin_pattern.match(value):
            return value
        return None

    def _normalize_passport(self, id_dict):
        """ Validate and normalize a passport data structure. """
        # NOTE: We may want to validate passport numbers better. Valid
        # country code?  Check for non-empty values, digits?
        issuer = id_dict['idLand'][:2]
        passport = id_dict['idNr']
        return '{}-{}'.format(issuer, passport)

    def __call__(self, employee_data):
        """
        :param dict employee_data:
            Normalized employee data.

        :returns generator:
            Valid Cerebrum (id_type, id_value) pairs
        """
        dfo_id = employee_data['id']
        yield 'DFO_PID', dfo_id

        nin = self._normalize_nin(employee_data.get('fnr'))
        if nin:
            yield 'NO_BIRTHNO', nin

        for other_id in employee_data.get('annenId', []):
            id_type = other_id.get('idType')

            if id_type == '02':
                # idType 02 is passport issuer and id
                passport = self._normalize_passport(other_id)
                if passport:
                    yield 'PASSNR', passport
                else:
                    logger.warning('ignoring invalid annenId.idType=02 '
                                   '(passport) data')
                continue

            logger.debug('ignoring unknown annenId.idType=%s', repr(id_type))


class DfoContactInfo(object):
    """
    Extract contact info from dfo employee data.

    >>> get_contacts = DfoContactInfo()
    >>> list(get_contacts({
    ...     'id': '01234567',
    ...     'telefonnummer': '22 85 50 50'}))
    [('PHONE', '+4722855050')]
    """

    # employee_data key -> cerebrum contact_info_type
    phone_key_map = collections.OrderedDict([
        # ('tjenestetelefon', ?),
        # ('privatTelefonnummer', ?),
        ('telefonnummer', 'PHONE'),
        ('mobilnummer', 'MOBILE'),
        ('mobilPrivat', 'PRIVATEMOBILE'),
        # ('privatTlfUtland', ?),
    ])

    def _normalize_phone(self, value):
        """ parse and normalize a phone number. """
        num = None
        for region in (None, 'NO'):
            try:
                num = phone_utils.parse(value, region=region)
                # TODO: Should *probably* call is_probable_number() here,
                # to avoid some obviously invalid phone numbers.
                #
                # The `Cerebrum.utils.phone` module needs some work too, as we
                # don't really have an abstraction for is_probable_number...
                #
                # Also, this _normalize_phone function should probably be
                # implemented in `Cerebrum.utils.phone` directly -- it's pretty
                # much the only thing we really need.
                break
            except phone_utils.NumberParseException:
                continue
        if num:
            return phone_utils.format(num)
        raise ValueError("Invalid phone number: " + repr(value))

    def __call__(self, employee_data):
        """
        :param dict employee_data:
            Normalized employee data

        :returns generator:
            Valid Cerebrum (contact_info_type, contact_info_value) pairs
        """
        dfo_id = employee_data['id']

        # Phone numbers
        for key, crb_type in self.phone_key_map.items():
            value = employee_data.get(key)
            if not value:
                continue
            try:
                phone = self._normalize_phone(value)
                yield crb_type, phone
            except ValueError:
                logger.warning("invalid %s for id=%s", key, dfo_id)

        # We don't have any other contact info types yet, but we should repeat
        # this for email-addresses, websites, ...


class DfoTitles(object):
    """
    Extract and map potential employee titles from dfo employee data.

    Extracts employee title (tittel) and main assignment title
    (stillingstittel), then translates these using the py:mod:`.title_maps`
    module.

    NOTE: The title mapping module is hard-coded to use the titles specified in
    a ``user_title_map`` module - usually placed adjacent to ``cereconf``.

    >>> get_titles = DfoTitles()
    >>> list(get_titles({
    ...     'id': '01234567',
    ...     'tittel': 'Fung.fak.dir',
    ...     'stillingId': '123',
    ...     'assignments': {'123': {'stillingstittel': '0214 R'}}}))
    [("PERSONALTITLE", "nb", "Fungerende fakultetsdirektør"),
     ("PERSONALTITLE", "en", "Acting Faculty Director"),
     ("WORKTITLE", "nb", "Rektor"),
     ("WORKTITLE", "en", "Rector")]
    """

    def __call__(self, employee_data):
        main_id = employee_data['stillingId']
        assignment = employee_data['assignments'].get(main_id)

        input_titles = (
            ('PERSONALTITLE', employee_data.get('tittel'),
             title_maps.personal_titles),
            ('WORKTITLE', (assignment or {}).get('stillingstittel'),
             title_maps.job_titles),
        )
        for variant, raw_value, t_map in input_titles:
            if not raw_value:
                continue

            localized = t_map.get(raw_value, {})
            if localized:
                for lang, value in localized.items():
                    yield (variant, lang, value)
            else:
                logger.warning('no translation for %s title %s',
                               variant, repr(raw_value))


class DfoAffiliations(object):
    """ Extract potential affiliations from dfo employee data.

    We map *all* assignments to a potential affiliation (if any -- invalid or
    unknown assignments are skipped).

    We say potential, as the assignment may not be valid at the current date,
    and the affiliated org unit may not be known.  It will be up to the import
    routine to decide if any of the resulting affiliations can be used.

    Note that this particular function *must* receive output from the employee
    dataparser, as it needs *both* employee info, *and* additional info on each
    assignment present on the employee object.
    """

    # A sequence of invalid assignment IDs.
    #
    # Any assignment with any of these IDs will simply be dropped, and not
    # considered further.
    IGNORE_ASSIGNMENT_IDS = (99999999,)

    # Employee group/subgroup to affiliation map.
    #
    # Employees are placed in groups (medarbeidergruppe, MG) and subgroups
    # (medarbeiderundergruppe, MUG).  If placed in any of the following
    # group/subgroup pairs, we should not consider the main assignment
    # category, but rather map to specific non-employee affiliations.
    EMPLOYEE_GROUP_MAP = {
        (8, 50): 'ANSATT/bilag',
        (9, 90): 'TILKNYTTET/ekst_partner',
        (9, 91): 'TILKNYTTET/ekst_partner',
        (9, 93): 'TILKNYTTET/emeritus',
        (9, 94): 'TILKNYTTET/ekst_partner',
        (9, 95): 'TILKNYTTET/gjesteforsker',
    }

    # Assignment category map
    #
    # Any assignment category in this map should map directly to a specific
    # employee affiliation.
    #
    # TODO: Do this *really* need to be configurable?  Or should we rather
    # implement subclasses with the proper categories?
    ASSIGNMENT_CATEGORY_MAP = {
        # Administrativt personale:
        50078118: "ANSATT/tekadm",

        # Drifts- og teknisk pers./andre tilsatte
        50078119: "ANSATT/tekadm",

        # Undervisnings- og forsknings personale
        50078120: "ANSATT/vitenskapelig",
    }

    @classmethod
    def _get_category_aff(cls, assignment):
        """
        Find a suitable category from assignment data.

        :type assignment: dict
        :param assignment: an assignment dict
        """
        # Do we need to consider assignment category start/end dates? And if
        # so, should grace/offsets be applied?  What does these dates even
        # mean?
        for category in assignment['stillingskat']:
            if category['stillingskatId'] in cls.ASSIGNMENT_CATEGORY_MAP:
                return cls.ASSIGNMENT_CATEGORY_MAP[category['stillingskatId']]
        return None

    def __call__(self, employee_data):
        """
        :param dict employee_data:
            Normalized employee + assignment data

        :returns generator:
            Valid Cerebrum (contact_info_type, contact_info_value) pairs
        """
        main_id = employee_data['stillingId']
        main_group = employee_data.get('medarbeidergruppe')
        main_subgroup = employee_data.get('medarbeiderundergruppe')
        main_start = employee_data['startdato']
        main_end = employee_data['sluttdato']

        # Let's deal with the main assignment first
        sort_by_main = make_priority_lookup((main_id,))
        assignment_ids = sorted(employee_data['assignments'], key=sort_by_main)

        for assignment_id in assignment_ids:
            if assignment_id in self.IGNORE_ASSIGNMENT_IDS:
                logger.info('skipping ignored assignment-id=%s', assignment_id)
                continue

            assignment = employee_data['assignments'][assignment_id]

            # Affiliation from category - "regular emplyee affs"
            aff = self._get_category_aff(assignment)

            if assignment_id == main_id:
                # TODO: should we look at the assignment['period']?
                start_date, end_date = main_start, main_end

                # If the person has one of the MG/MUG combinations present in
                # role mapping, then the main assignment should be handled as
                # a special affiliation.
                if (main_group, main_subgroup) in self.EMPLOYEE_GROUP_MAP:
                    aff = self.EMPLOYEE_GROUP_MAP[(main_group, main_subgroup)]
                elif not aff:
                    # If this happens it's probably because the assignment
                    # doesn't yet have a valid category.  There's really
                    # nothing we can do at this point though - we don't know
                    # which affiliation to assign to the employee.
                    logger.warning(
                        "Unknown main assignment: id=%r, mg=%r, mug=%r",
                        assignment_id, main_group, main_subgroup)
                    continue

            else:
                start_date = assignment['startdato']
                end_date = assignment['sluttdato']

                if not aff:
                    # Same as for main assignment above - no valid
                    # stillingskat.stillingskatId.
                    logger.warning("Unknown secondary assignment: id=%r",
                                   assignment_id)
                    continue

            if not aff:
                # We've should have covered all bases here, but let's make
                # entirely sure.
                raise RuntimeError("no aff set - this shouldn't happen")

            if not assignment.get('organisasjonId'):
                logger.warning("Missing location for assignment: "
                               "id=%r, aff=%r", assignment_id, aff)
                continue

            ou_ids = [
                ('DFO_OU_ID', assignment['organisasjonId']),
            ]

            yield (aff, ou_ids, start_date, end_date)


class EmployeeMapper(AbstractMapper):
    """A simple employee mapper class"""

    get_contact_info = DfoContactInfo()
    get_person_ids = DfoPersonIds()
    get_affiliations = DfoAffiliations()
    get_titles = DfoTitles()

    @staticmethod
    def get_names(employee_data):
        """
        Get names for a given person.

        :returns generator:
            Valid Cerebrum (name_type, name_value) pairs
        """
        fn = employee_data.get('fornavn', '')
        ln = employee_data.get('etternavn', '')
        if fn:
            yield ('FIRST', fn)
        if ln:
            yield ('LAST', ln)

    @staticmethod
    def get_gender(employee_data):
        """
        Get names of a given person.

        :returns str:
            "M", "F", or "X" if missing/unknown gender value.
        """
        gender = employee_data.get('kjonn')
        if gender in ('M', 'F'):
            return gender
        logger.debug('unknown gender for id=%r: %r',
                     employee_data['id'], gender)
        return 'X'

    def translate(self, reference, employee_data):
        person = HrPerson(
            hr_id=employee_data['id'],
            birth_date=employee_data['fdato'],
            gender=self.get_gender(employee_data),
            enable=employee_data['eksternbruker'] or True,
        )

        if employee_data['startdato']:
            person.start_date = employee_data['startdato']
        else:
            logger.debug("no startdate registered for %s", person.hr_id)

        person.ids.extend(self.get_person_ids(employee_data))
        person.contacts.extend(self.get_contact_info(employee_data))
        person.names.extend(self.get_names(employee_data))
        person.titles.extend(self.get_titles(employee_data))
        person.affiliations.extend(self.get_affiliations(employee_data))

        return person

    def get_active_affiliations(self, hr_object, _today=None):
        today = _today or datetime.date.today()

        def _add_delta(dt, d):
            # add a timedelta, but ignore out of bounds results
            try:
                return dt + d
            except OverflowError:
                return dt

        # TODO: What if we have *two* different ANSATT/<some-ou> affs from this
        # function?  We should probably define some ordering and exclude
        # "duplicated" aff-statuses by some criteria, e.g.:
        #
        # - keep whichever aff/status with the earliest start-date?
        # - define some sort of status priority list, so that e.g.
        #   ANSATT/vitenskapelig always trumps ANSATT/tekadm?
        #
        # Currently, if both ANSATT/vitenskapelig@x and ANSATT/tekadm@x is
        # passed to the AffiliationSync, the first one listed will be
        # INSERTed/UPDATEed, and the second will UPDATE the first with a new
        # status.
        #
        # This is also probably behaviour that should be implemented in the
        # *importer*?

        for aff, ou, start_date, end_date in hr_object.affiliations:
            if start_date:
                start_limit = _add_delta(start_date, self.start_offset)
                if today < start_limit:
                    continue

            if end_date:
                end_limit = _add_delta(end_date, self.end_offset)
                if today > end_limit:
                    continue

            yield aff, ou

    def is_active(self, hr_object):
        if not hr_object.enable:
            return False

        return any(self.get_active_affiliations(hr_object))
