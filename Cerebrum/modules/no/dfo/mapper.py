# -*- coding: utf-8 -*-
#
# Copyright 2020-2024 University of Oslo, Norway
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
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import collections
import datetime
import logging
import re

from Cerebrum.modules.hr_import.mapper import AbstractMapper, HrPerson
from Cerebrum.utils import phone as phone_utils
from Cerebrum.utils import reprutils
from Cerebrum.utils.mappings import SimpleMap
from Cerebrum.utils.sorting import make_priority_lookup


logger = logging.getLogger(__name__)


LANGUAGES = ('nb', 'en')


def get_localized_data(value, languages=LANGUAGES, warn=False):
    """
    Prepare/normalize a localized dict.

    >>> get_localized_data({'en': "", 'nb': "bar", 'nn': "xyz"})
    {'nb': "bar"}
    """
    value = value or {}
    names = {}
    for lang in languages:
        if value.get(lang):
            names[lang] = value[lang]
    if warn:
        missing = set(languages) - set(names)
        if missing:
            logger.warning('incomplete translation (missing %s): %s',
                           (', '.join(missing), repr(value)))
    return names


class _SizedMap(reprutils.ReprFieldMixin, SimpleMap):
    """
    Mixin that adds a size repr field for SimpleMap classes.

    >>> repr(_SizedMap({'foo': 3, 'bar': 42,}))
    "<_SizedMap size=2>"
    """
    repr_id = False
    repr_module = False
    repr_fields = ("size",)

    @property
    def size(self):
        return len(self)


class _LocalizedMap(_SizedMap):
    def transform_value(self, value):
        return get_localized_data(value, warn=True)


class AffiliationMap(_SizedMap):
    """
    Affiliation mapping.

    Maps code tuples (e.g. MG/MUG) or codes (e.g. stillingskode, stillingskat)
    to affiliations.
    """
    def transform_key(self, value):
        if isinstance(value, tuple):
            return tuple(int(i) for i in value)
        return int(value)

    def transform_value(self, value):
        if value is None:
            # Explicit hit, but no value.  This means means that the key
            # is *valid*,  but should explicitly not map to an affiliation.
            return None
        if len(value.split("/")) != 2:
            raise ValueError("Invalid affiliation: " + repr(value))
        return value


class AssignmentTitleMap(_LocalizedMap):
    """
    A map of assignment code (stillingskode) to localized title.

    >>> titles = AssignmentTitleMap({
    ...     20000214: {'nb': 'Rektor', 'en': 'Rector'},
    ...     20000787: {'nb': "Spesialtannlege", 'en': "Specialist Dentist"},
    ... })
    >>> titles['20000214']
    {'nb': 'Rektor', 'en': 'Rector'}
    """
    def transform_key(self, value):
        return int(value)


class PersonalTitleMap(_LocalizedMap):
    """
    A map of personal title ids to personal title.

    A personal title id is a shortened, norwegian title from the source system.

    >>> titles = PersonalTitleMap({
    ...     "Fung.fak.dir": {
    ...         'nb': "Fungerende fakultetsdirektør",
    ...         'en': "Acting Faculty Director",
    ...     },
    ...     "Fung.forsk.led": {
    ...         'nb': "Fungerende forskningsleder",
    ...         'en': "Acting Head of Research",
    ...     }})
    >>> titles['Fung.fak.dir']
    {'nb': "Fungerende fakultetsdirektør", 'en': "Acting Faculty Director"}
    """


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
        if not id_dict.get('idLand'):
            logger.debug('invalid annenId.idType=02 (passport) - no idLand')
            return None
        if not id_dict.get('idNr'):
            logger.debug('invalid annenId.idType=02 (passport) - no idNr')
            return None
        # NOTE: We may want to validate passport numbers better. Valid
        # country code? Valid travel id/passport number?
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
    (stillingstittel), then translates these using the mappings defined in this
    class.  Note: This default implementation has no mappings - see relevant
    subclasses.

    >>> get_titles = DfoTitles()
    >>> list(get_titles({
    ...     'id': '01234567',
    ...     'tittel': 'Fung.fak.dir',
    ...     'stillingId': '123',
    ...     'assignments': {'123': {'stillingskode': 20000214}}}))
    [("PERSONALTITLE", "nb", "Fungerende fakultetsdirektør"),
     ("PERSONALTITLE", "en", "Acting Faculty Director"),
     ("WORKTITLE", "nb", "Rektor"),
     ("WORKTITLE", "en", "Rector")]
    """

    work_title_map = AssignmentTitleMap({})
    personal_title_map = PersonalTitleMap({})

    def __call__(self, employee_data):
        main_id = employee_data.get('stillingId')
        assignments = employee_data.get('assignments') or {}
        assignment = assignments.get(main_id)

        input_titles = (
            ('PERSONALTITLE', employee_data.get('tittel'),
             self.personal_title_map),
            ('WORKTITLE', (assignment or {}).get('stillingskode'),
             self.work_title_map),
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
    """
    Get affiliations from employee data.

    This class tries to map all assignments to affiliations.

    Note that the assignment may not be valid at the current date, and the
    affiliated org unit may not be known.  It will be up to the import
    routine to decide if and how any of the resulting affiliations are used.

    As with the other mappers, the input object must come from the datasource
    module.  This is especially important here, as the input object must be
    patched with assignment data.
    """

    # Employee group/subgroup to affiliation map.
    #
    # Employees are placed in groups (medarbeidergruppe, MG) and subgroups
    # (medarbeiderundergruppe, MUG).  If placed in any of the following
    # group/subgroup pairs, we should not consider the main assignment
    # category or code, but rather map to specific affiliations.
    #
    # If a mapping is explicitly set to `None`, no other mappings will be
    # considered either, and the assignment won't map to any affiliation.
    employee_group_map = AffiliationMap({
        # Assignment group (MG/MUG) to affiliation, e.g.:
        # (8, 50): None,
        # (9, 90): "TILKNYTTET/ekst_partner",
    })

    # Assignment code to affiliation map.
    #
    # Any assignment code (stillingskode) in this map will directly map to the
    # given affiliation.  If the assignment code *isn't* mapped here, we'll
    # fall back to checking the assignment category.  If the code is explicitly
    # set to `None`, the category won't be checked, and the assignment won't
    # map to any affiliation.
    assignment_code_map = AffiliationMap({
        # Assignment code to affiliation, e.g.:
        # 20000214: "Ansatt/tekadm",
    })

    # Assignment category to affiliation map
    #
    # Any assignment category (stillingskat) in this map will directly map to
    # the given affiliation (assuming the employee group and assignment code
    # failed to do so).
    assignment_category_map = AffiliationMap({
        # Assignment category to affiliation, e.g.:
        # 50078118: "ANSATT/tekadm",
    })

    def _get_aff_from_assignment(self, assignment):
        """
        Find a suitable affiliation from assignment data.

        :type assignment: dict
        :param assignment: an assignment dict
        """
        assignment_id = assignment['id']
        assignment_code = assignment['stillingskode']
        if assignment_code in self.assignment_code_map:
            # The code may explicitly be set to None, which means we shouldn't
            # try to match stillingskat.
            logger.debug(
                "Found assignment affiliation from code: %r -> %r",
                assignment_code, self.assignment_code_map[assignment_code])
            return self.assignment_code_map[assignment_code]

        # Unknown assignment code (stillingskode), try to find a assingment
        # category (stillingskat):
        logger.debug("Unknown assignment code: id=%r, code=%r",
                     assignment_id, assignment_code)
        # We may want to filter out catetories based on their start and end
        # dates here?
        category_ids = [c['stillingskatId']
                        for c in assignment['stillingskat']]
        for category_id in category_ids:
            if category_id in self.assignment_category_map:
                logger.debug(
                    "Found assignment affiliation from category: %r -> %r",
                    category_id, self.assignment_category_map[category_id])
                return self.assignment_category_map[category_id]

        # Unknown assignment category as well, we can't find a valid
        # affiliation here...
        logger.debug("Unknown assignment category: id=%r, categories=%r",
                     assignment_id, category_ids)
        return None

    def __call__(self, employee_data):
        """
        :param dict employee_data:
            Normalized employee + assignment data

        :returns generator:
            Valid Cerebrum (contact_info_type, contact_info_value) pairs
        """
        main_id = employee_data.get('stillingId')
        main_group = employee_data.get('medarbeidergruppe')
        main_subgroup = employee_data.get('medarbeiderundergruppe')
        main_start = employee_data.get('startdato')
        main_end = employee_data.get('sluttdato')
        assignments = employee_data.get('assignments') or []

        # Let's deal with the main assignment first
        sort_by_main = make_priority_lookup((main_id,))
        assignment_ids = sorted(assignments, key=sort_by_main)

        for assignment_id in assignment_ids:
            assignment = assignments[assignment_id]

            # Affiliation from category - "regular emplyee affs"
            aff = self._get_aff_from_assignment(assignment)

            if assignment_id == main_id:
                # TODO: should we look at the assignment['period'] in stead?
                start_date, end_date = main_start, main_end

                # For the main assignment only:  Use the employee group mapping
                # if the given employee group is mapped.
                if (main_group, main_subgroup) in self.employee_group_map:
                    aff = self.employee_group_map[(main_group, main_subgroup)]
                    if not aff:
                        logger.info(
                            "Ignoring assignment from MG/MUG: "
                            "id=%r, mg=%r, mug=%r",
                            assignment_id, main_group, main_subgroup)
                        continue
                elif not aff:
                    # This shouldn't really happen:  If we get here, then none
                    # of the mappers can find an appropriate affiliation.
                    # We're probably missing an assignment code mapping.
                    logger.warning(
                        "Unknown main assignment: id=%r, mg=%r, mug=%r",
                        assignment_id, main_group, main_subgroup)
                    continue

            else:
                start_date = end_date = None
                for secondary in (employee_data.get('tilleggsstilling') or ()):
                    if assignment_id != secondary['stillingId']:
                        continue
                    start_date = secondary['startdato']
                    end_date = secondary['sluttdato']
                    break

                if not aff:
                    # Same as for main assignment above - we can't find a an
                    # affiliation for the input data.
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
            birth_date=employee_data.get('fdato'),
            gender=self.get_gender(employee_data),
            # eksternbruker=False -> shouldn't get a user account, i.e. we
            # don't need any information in Cerebrum.
            # Note: This is a dangerous field - if misinterpreted, all employee
            # roles could be removed.
            enable=employee_data.get('eksternbruker', True),
        )

        if employee_data.get('startdato'):
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
            # Add a timedelta, but ignore out of bounds results.  This is a bit
            # hacky, but OverflowError means the result is so far into the past
            # or the future that any offset we're adding isn't really relevant.
            try:
                return dt + d
            except OverflowError:
                return dt

        # Each person can only have *one* main affiliation type (e.g.  ANSATT)
        # per <ou> from a given source system.  If we find both
        # ANSATT/vitenskapelig@<ou> and ANSATT/tekadm@<ou> in the employee
        # data, only *one* of the statuses can be stored in Cerebrum for a
        # given employee.
        #
        # If we pass both to AffiliationSync, only the second one (last to
        # be written), will be kept.  This is likely the opposite of what
        # we want, as the main assignment will be yielded first.
        seen_affs = set()

        for aff, ou, start_date, end_date in hr_object.affiliations:

            if start_date:
                start_limit = _add_delta(start_date, self.start_offset)
                if today < start_limit:
                    continue

            if end_date:
                end_limit = _add_delta(end_date, self.end_offset)
                if today > end_limit:
                    continue

            key = (aff.split("/", 1)[0], dict(ou)['DFO_OU_ID'])
            if key in seen_affs:
                logger.info("Skipping duplicate affiliation %s @ %s",
                            aff, repr(ou))
                continue
            seen_affs.add(key)

            yield aff, ou

    def is_active(self, hr_object, _today=None):
        if not hr_object.enable:
            return False

        return any(self.get_active_affiliations(hr_object, _today=_today))
