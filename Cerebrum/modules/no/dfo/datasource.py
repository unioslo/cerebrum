# -*- coding: utf-8 -*-
#
# Copyright 2020-2023 University of Oslo, Norway
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
DFØ-SAP datasource for HR imports.

This module contains utils to convert and validate relevant objects from DFØ.
Its main parts are:

py:func:`.parse_message`
    Convert an event payload to a simple dict with relevant items (event id,
    source, type, references) for later processing.

py:class:`.EmployeeDatasource`
    Convert and normalize person info + any referenced assignments.

py:class:`.AssignmentDatasource`
    Convert and normalize a single assignment from DFØ.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime
import json
import logging

import six

from Cerebrum.modules.hr_import.datasource import (
    AbstractDatasource,
    DatasourceInvalid,
)
from Cerebrum.utils import date as date_utils
from Cerebrum.utils import textnorm
from Cerebrum.utils.date_compat import get_datetime_tz

logger = logging.getLogger(__name__)


IGNORE_ASSIGNMENT_IDS = set((
    # placeholder for previous employees (invalid assignment):
    99999999,
))


def normalize_id(dfo_id):
    """ Get a normalized employee object id. """
    return six.text_type(int(dfo_id))


def normalize_text(value, allow_empty=False):
    """ Get a normalized, non-empty text (or None). """
    if value and not isinstance(value, six.string_types):
        value = six.text_type(value)
    if not value or not value.strip():
        if allow_empty:
            return None
        else:
            raise ValueError('empty text')
    return textnorm.normalize(value.strip())


def assert_bool(value):
    """ Verify value is a `bool`. """
    if value in (True, False):
        return value
    raise ValueError("invalid value: " + repr(value))


def assert_int(value, allow_empty=False):
    """ Verify value is an `int`. """
    if value in (None, ""):
        if allow_empty:
            return None
        else:
            raise ValueError('missing number')
    return int(value)


def assert_list(value):
    """
    Normalize list values.

    This is a work-around for the variable list-values we sometimes get from
    dfo.  This function ensures that the given value is a list:

    - If a non-list value is given, it will be wrapped in a list
    - None-values are filtered out

    >>> [assert_list(x) for x in (None, 1, [1, None, 2, 3])]
    [[], [1], [1, 2, 3]]
    """
    if not value:
        return []

    if not isinstance(value, list):
        value = [value]
    return [x for x in value if x is not None]


def assert_digits(value, allow_empty=False):
    """ Normalize text with only digits. """
    digits = normalize_text(value, allow_empty=allow_empty)
    if digits and not digits.isdigit():
        raise ValueError("invalid number string")
    return digits


def parse_dfo_date(value, allow_empty=True):
    """ Get a date object from a DFO date value. """
    if value:
        return date_utils.parse_date(value)
    elif allow_empty:
        return None
    else:
        raise ValueError('No date: %r' % (value,))


def _get_msg_id(d):
    """ parse 'id' field from message dict. """
    if 'id' not in d:
        raise DatasourceInvalid("missing 'id' field: %r" % (d,))
    return d['id']


def _get_msg_uri(d):
    """ parse 'uri' field from message dict. """
    if 'uri' not in d:
        raise DatasourceInvalid("missing 'uri' field: %r" % (d,))
    return d['uri']


def _get_msg_nbf(d):
    """ parse 'gyldigEtter' (nbf) field from message dict. """
    obj_nbf = d.get('gyldigEtter')
    if not obj_nbf:
        return None
    try:
        return get_datetime_tz(parse_dfo_date(obj_nbf))
    except Exception as e:
        raise DatasourceInvalid("invalid 'gyldigEtter' field: %s (%r, %r)"
                                % (e, obj_nbf, d))


def parse_message(msg_text):
    """ Parse DFØ-SAP message.

    :param str msg_text: json encoded message

    :rtype: dict
    :return:
        Returns a dict with message fields:

        - id (str): object id
        - uri (str): object type
        - nbf (datetime): not before (or None if not given)
    """
    try:
        msg_data = json.loads(msg_text)
    except Exception as e:
        raise DatasourceInvalid('invalid message format: %s (%r)' %
                                (e, msg_text))

    return {
        'id': _get_msg_id(msg_data),
        'uri': _get_msg_uri(msg_data),
        'nbf': _get_msg_nbf(msg_data),
    }


def parse_employee(d):
    """ Sanitize and normalize assignment data """
    result = {
        # External ids:
        'id': normalize_id(d['id']),
        'fnr': assert_digits(d.get('fnr'), allow_empty=True),
        'annenId': assert_list(d.get('annenId')),

        # Dfo identifier types not in use, but useful for debugging.
        #
        # brukerident and dfoBrukerident are internal dfo usernames.
        # eksternIdent should (in time) get updated with a Cerebrum username in
        # the cererbum-to-dfo integration
        'brukerident': normalize_text(d.get('brukerident'), allow_empty=True),
        'dfoBrukerident': normalize_text(d.get('dfoBrukerident'),
                                         allow_empty=True),
        'eksternIdent': normalize_text(d.get('eksternIdent'),
                                       allow_empty=True),

        # Basic person info
        'fornavn': normalize_text(d.get('fornavn'), allow_empty=True),
        'etternavn': normalize_text(d.get('etternavn'), allow_empty=True),
        'fdato': parse_dfo_date(d.get('fdato'), allow_empty=True),
        'kjonn': normalize_text(d.get('kjonn')),

        # Main employment info
        'stillingId': assert_int(d['stillingId']),
        'medarbeidergruppe': assert_int(d.get('medarbeidergruppe'),
                                        allow_empty=True),
        'medarbeiderundergruppe': assert_int(d.get('medarbeiderundergruppe'),
                                             allow_empty=True),
        'startdato': parse_dfo_date(d['startdato'], allow_empty=True),
        'sluttdato': parse_dfo_date(d['sluttdato'], allow_empty=True),
        'tittel': normalize_text(d.get('tittel'), allow_empty=True),

        # custom field 'eksternbruker' - the employee should exist in systems
        # outside dfo
        'eksternbruker': assert_bool(d.get('eksternbruker', True)),

        # custom field 'lederflagg' - the employee main assignment is a
        # department head position
        'lederflagg': assert_bool(d.get('lederflagg', False)),

        # custom field 'reservasjonPublisering' - the employee should be
        # omitted in public listings
        'reservasjonPublisering': assert_bool(d.get('reservasjonPublisering')
                                              or False),

    }

    # Contact info fields
    result.update({
        k: normalize_text(d.get(k), allow_empty=True)
        for k in (
            # 'epost',  # not in use
            'mobilPrivat',
            'mobilnummer',
            # 'privatEpost',  # not in use
            'privatTelefonnummer',
            'privatTlfUtland',
            'telefonnummer',
            'tjenestetelefon',
        )
    })

    # Process secondary assignments
    secondary = result['tilleggsstilling'] = []
    for item in assert_list(d.get('tilleggsstilling')):
        secondary.append({
            'stillingId': assert_int(item['stillingId']),
            'startdato': parse_dfo_date(item['startdato'], allow_empty=True),
            'sluttdato': parse_dfo_date(item['sluttdato'], allow_empty=True),
            # 'dellonnsprosent',  # ignored
        })

    # Other, ignored fields:
    # - dellonnsprosent
    # - endretAv
    # - endretDato
    # - endretInfotype
    # - endretKlokkeslett
    # - hjemmelKode
    # - hjemmelTekst
    # - jurBedriftsnummer
    # - kostnadssted
    # - landkode
    # - organisasjonId
    # - pdo
    # - portaltilgang
    # - privatPostadresse
    # - privatPostnr
    # - privatPoststed
    # - sakarkivnr
    # - sluttarsak
    # - turnustilgang
    return result


def parse_assignment(d):
    """
    Sanitize and normalize assignment data.
    """
    result = {
        'id': assert_int(d['id']),
        'stillingskode': assert_digits(d['stillingskode'],
                                       allow_empty=True),
        'stillingstittel': normalize_text(d.get('stillingstittel'),
                                          allow_empty=True),
        'organisasjonId': assert_digits(d['organisasjonId'],
                                        allow_empty=True),
        # 'stillingsnavn': None,  # ignored
        # 'yrkeskode': None,  # ignored
        # 'yrkeskodetekst': None,  # ignored
    }

    # Process employees
    assigned = result['innehaver'] = []
    for emp in assert_list(d.get('innehaver')):
        assigned.append({
            'innehaverAnsattnr': normalize_id(emp['innehaverAnsattnr']),
            'innehaverStartdato': parse_dfo_date(emp['innehaverStartdato'],
                                                 allow_empty=True),
            'innehaverSluttdato': parse_dfo_date(emp['innehaverSluttdato'],
                                                 allow_empty=True),
        })

    # Alternate view of employees (map employee to start- and end-date ranges)
    # TODO: Is this needed?  Should probably be moved to a mapper
    employees = result['employees'] = {}
    for emp in assigned:
        ranges = employees.setdefault(emp["innehaverAnsattnr"], [])
        ranges.append((emp["innehaverStartdato"], emp["innehaverSluttdato"]))

    # Process categories
    categories = result['stillingskat'] = []
    for cat_d in assert_list(d.get('stillingskat')):
        categories.append({
            'stillingskatId': assert_int(cat_d['stillingskatId']),
            'stillingskatStartdato': parse_dfo_date(
                cat_d['stillingskatStartdato'], allow_empty=True),
            'stillingskatSluttdato': parse_dfo_date(
                cat_d['stillingskatSluttdato'], allow_empty=True),
            # - stillingskatBetegn
        })

    # Collect a simplified list of categories for assignment
    # TODO: Is this really needed?  Should probably be moved to a mapper
    cat = result['category'] = []
    for cat_d in categories:
        cat.append(cat_d['stillingskatId'])
    return result


def get_assignment_ids(employee_data):
    """
    Collect all relevant assignment ids from employee.
    """
    if employee_data.get('stillingId'):
        yield assert_int(employee_data['stillingId'])
    for secondary in employee_data.get('tilleggsstilling', ()):
        if secondary and secondary.get('stillingId'):
            yield assert_int(secondary['stillingId'])


def prepare_employee_data(raw_employee_data, raw_assignments_data):
    """
    Parse and combine employee data and assignment data.

    :param dict raw_employee_data:
        JSON result for an employee

    :param dict raw_assignments_data:
        A list of JSON results for each relevant assignment

    :return dict:
        Returns a sanitized/normalized employee data dict, with an extra
        'assignments' key, which maps assignment ids to
        sanitized/normalized assignmnent data dicts.
    """
    employee = parse_employee(raw_employee_data)
    employee.update({'assignments': {}})
    logger.debug('employee: %r', employee['id'])

    # Collect assignment ids from employee
    assignment_ids = set(get_assignment_ids(employee))
    logger.debug('employee assignments: %r', assignment_ids)

    # Map assignment ids to raw assignment data
    assignment_map = {assert_int(d['stilling']['id']): d['stilling']
                      for d in raw_assignments_data}
    logger.debug('assignments: %r', set(assignment_map))

    for assignment_id in assignment_ids:
        if assignment_id not in assignment_map:
            # this should never happen - employee has a given assingnment
            # id, but we haven't looked it up/collected it
            raise RuntimeError("No data on assignment id: "
                               + repr(assignment_id))

        # Parse assignment and add to employee assignment map
        assignment = parse_assignment(assignment_map[assignment_id])

        # TODO: temporary check to catch a potential issue/gotcha -- is it
        # possible for a given employee to somehow get the same assignment-id
        # twice?  E.g. in two different time intervals?
        #
        # If so, this assignments dict should really be a list, and we need
        # some extra date processing/fixes when we look at this data later.
        if assignment_id in employee['assignments']:
            logger.warning(
                "Oops: employee-id=%r has been assigned assignment-id=%r more "
                "than once.  This isn't really well specified or handled...",
                employee['id'], assignment_id)

        employee['assignments'][assignment_id] = assignment

    return employee


def _unpack_list_item(value):
    """ Unpack a single value wrapped in a list. """
    if not value:
        raise ValueError("empty list")
    value = assert_list(value)
    if len(value) != 1:
        raise ValueError("invalid number of objects: " + str(len(value)))
    return value[0]


class EmployeeDatasource(AbstractDatasource):

    def __init__(self, client):
        self.client = client

    def get_reference(self, event):
        """ Extract reference from message body """
        return parse_message(event.body)['id']

    def _get_employee(self, employee_id, date=None):
        raw = self.client.get_employee(employee_id, date=date)
        try:
            raw = _unpack_list_item(raw)
        except ValueError as e:
            logger.warning('no result for employee-id %s (%s)',
                           repr(employee_id), str(e))
            return {}
        return parse_employee(raw)

    def _get_assignment(self, employee_id, assignment_id):
        raw = self.client.get_stilling(assignment_id)
        try:
            raw = _unpack_list_item(raw)
        except ValueError as e:
            logger.warning('no result for assignment-id %s (%s)',
                           repr(assignment_id), str(e))
            return {}
        return parse_assignment(raw)

    def get_object(self, reference, _today=None):
        """ Fetch data from sap (employee data, assignments, roles). """
        employee_id = reference
        today = _today or datetime.date.today()
        assignment_ids = set()
        employee = self._get_employee(employee_id)

        # Try to find employee data and assignments at different dates
        deltas = [datetime.timedelta(days=3)]
        for delta in deltas:
            date = today + delta
            logger.debug("supplement with data from %s", date)
            shifted = self._get_employee(employee_id, date=date)
            if shifted:
                if not employee:
                    employee = shifted
                # Assignments already includes data on previous/upcoming
                # employees, so there's no need to include a date in these
                # lookups
                assignment_ids.update(get_assignment_ids(shifted))

        if not employee:
            return {'id': normalize_id(employee_id)}

        assignment_ids.update(get_assignment_ids(employee))

        # Exclude any assignment we're not interested in:
        #   1. These assignments will never lead to an affiliation
        #   2. Persons with just these assignments aren't considered employees
        #   3. We don't want to spend time looking up these assignments
        assignment_ids = assignment_ids - IGNORE_ASSIGNMENT_IDS

        assignments = employee['assignments'] = {}
        for assignment_id in assignment_ids:
            assignment = self._get_assignment(employee_id, assignment_id)
            if not assignment:
                logger.warning('no result for assignment-id %r', assignment_id)
                continue
            assignments[assignment_id] = assignment

        return employee

    @classmethod
    def prepare_object(cls, *args, **kwargs):
        """
        Dummy version of `get_object`

        For when we already have employee and assignment data.
        """
        return prepare_employee_data(*args, **kwargs)


class AssignmentDatasource(AbstractDatasource):

    def __init__(self, client):
        self.client = client

    def get_reference(self, event):
        """ Extract reference from message body """
        return parse_message(event.body)['id']

    def _get_assignment(self, assignment_id):
        raw = self.client.get_stilling(assignment_id)
        try:
            raw = _unpack_list_item(raw)
        except ValueError as e:
            logger.warning('no result for assignment-id %s (%s)',
                           repr(assignment_id), str(e))
            return {}
        return parse_assignment(raw)

    def get_object(self, reference):
        """ Fetch data from sap (employee data, assignments, roles). """
        assignment = self._get_assignment(reference)
        if not assignment:
            raise DatasourceInvalid('No assignment_id=%r found' %
                                    (reference,))
        return assignment
