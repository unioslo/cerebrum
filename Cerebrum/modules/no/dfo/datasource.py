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
DFØ-SAP datasource for HR imports.
"""
from __future__ import unicode_literals

import json
import logging

from Cerebrum.modules.hr_import.datasource import (
    AbstractDatasource,
    DatasourceInvalid,
    RemoteObject,
)
from Cerebrum.modules.no.dfo.utils import (
    assert_list,
    parse_date,
    parse_employee_id
)
from Cerebrum.utils.date_compat import get_datetime_tz

logger = logging.getLogger(__name__)


def _get_id(d):
    """ parse 'id' field from message dict. """
    if 'id' not in d:
        raise DatasourceInvalid("missing 'id' field: %r" % (d,))
    return d['id']


def _get_uri(d):
    """ parse 'uri' field from message dict. """
    if 'uri' not in d:
        raise DatasourceInvalid("missing 'uri' field: %r" % (d,))
    return d['uri']


def _get_nbf(d):
    """ parse 'gyldigEtter' (nbf) field from message dict. """
    obj_nbf = d.get('gyldigEtter')
    if not obj_nbf:
        return None
    try:
        return get_datetime_tz(parse_date(obj_nbf))
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
        'id': _get_id(msg_data),
        'uri': _get_uri(msg_data),
        'nbf': _get_nbf(msg_data),
    }


class Employee(RemoteObject):
    pass


class Assignment(RemoteObject):
    pass


class Person(RemoteObject):
    pass


def parse_employee(employee_d):
    """ Sanitize and normalize assignment data """
    # TODO: Filter out unused fields, normalize the rest
    result = dict(employee_d)
    result.update({
        'startdato': parse_date(employee_d['startdato'], allow_empty=True),
        'sluttdato': parse_date(employee_d['sluttdato']),
        'tilleggsstilling': [],
    })
    for assignment in assert_list(employee_d.get('tilleggsstilling')):
        result['tilleggsstilling'].append({
            'stillingId': assignment['stillingId'],
            'startdato': parse_date(assignment['startdato'], allow_empty=True),
            'sluttdato': parse_date(assignment['sluttdato'], allow_empty=True),
        })
    return result


def parse_assignment(assignment_d):
    """
    Sanitize and normalize assignment data.
    """
    # TODO: remove unused fields
    result = {
        'id': assignment_d['id'],
        'organisasjonId': assignment_d['organisasjonId'],
        'stillingskode': assignment_d['stillingskode'],
        'stillingsnavn': assignment_d['stillingsnavn'],
        'stillingstittel': assignment_d['stillingstittel'],
        'yrkeskode': assignment_d['yrkeskode'],
        'yrkeskodetekst': assignment_d['yrkeskodetekst'],
        'category': [],
    }
    for cat_d in assert_list(assignment_d.get('stillingskat')):
        result['category'].append(cat_d['stillingskatId'])

    employees = {}
    for member_d in assert_list(assignment_d.get('innehaver')):
        if member_d['innehaverAnsattnr'] not in employees:
            employees[member_d['innehaverAnsattnr']] = []
        employees[member_d['innehaverAnsattnr']].append((
            parse_date(member_d.get('innehaverStartdato'), allow_empty=True),
            parse_date(member_d.get('innehaverSluttdato'), allow_empty=True),
        ))

    result['employees'] = employees
    return result


class EmployeeDatasource(AbstractDatasource):

    def __init__(self, client):
        self.client = client

    def get_reference(self, event):
        """ Extract reference from message body """
        return parse_message(event.body)['id']

    def _get_employee(self, employee_id):
        raw = self.client.get_employee(employee_id)
        if not raw:
            logger.warning('no result for employee-id %r', employee_id)
            return {}

        if isinstance(raw, list) and len(raw) == 1:
            result = parse_employee(raw[0])
        else:
            result = parse_employee(raw)
        return result

    def _get_assignment(self, employee_id, assignment_id):
        raw = self.client.get_stilling(assignment_id)
        if not raw:
            logger.warning('no result for assignment-id %r', assignment_id)
            return {}
        return parse_assignment(raw)

    def get_object(self, reference):
        """ Fetch data from sap (employee data, assignments, roles). """
        employee_id = reference
        employee_data = self._get_employee(employee_id)

        employee = {
            'id': parse_employee_id(reference),
            'employee': {},
            'assignments': {},
        }

        if employee_data:
            employee['employee'] = Person('dfo-sap', reference, employee_data)
            assignment_ids = {employee_data['stillingId']}

            for secondary_assignment in employee_data['tilleggsstilling']:
                assignment_ids.add(secondary_assignment['stillingId'])

            for assignment_id in assignment_ids:
                assignment = self._get_assignment(employee_id, assignment_id)

                if assignment:
                    employee['assignments'][assignment_id] = (
                        Assignment('dfo-sap', assignment_id, assignment)
                    )
                else:
                    raise DatasourceInvalid('No assignment_id=%r found' %
                                            (assignment_id,))

        return Employee('dfo-sap', reference, employee)


class AssignmentDatasource(AbstractDatasource):

    def __init__(self, client):
        self.client = client

    def get_reference(self, event):
        """ Extract reference from message body """
        return parse_message(event.body)['id']

    def _get_assignment(self, assignment_id):
        raw = self.client.get_stilling(assignment_id)
        if not raw:
            logger.error('no result for assignment-id %r', assignment_id)
            return {}
        return parse_assignment(raw)

    def get_object(self, reference):
        """ Fetch data from sap (employee data, assignments, roles). """
        assignment = self._get_assignment(reference)
        if not assignment:
            raise DatasourceInvalid('No assignment_id=%r found' %
                                    (reference,))
        return Assignment('dfo-sap', reference, assignment)
