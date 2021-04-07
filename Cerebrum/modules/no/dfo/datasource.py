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
from Cerebrum.modules.no.dfo.utils import assert_list
from Cerebrum.utils.date import parse_date, now
from Cerebrum.utils.date_compat import get_datetime_tz


logger = logging.getLogger(__name__)


def _get_id(d):
    """ parse 'id' field from message dict. """
    if 'id' not in d:
        raise DatasourceInvalid("missing 'id' field")
    return d['id']


def _get_uri(d):
    """ parse 'uri' field from message dict. """
    if 'uri' not in d:
        raise DatasourceInvalid("missing 'uri' field")
    return d['uri']


def _get_nbf(d):
    """ parse 'gyldigEtter' (nbf) field from message dict. """
    obj_nbf = d.get('gyldigEtter')
    if not obj_nbf:
        return None
    try:
        return get_datetime_tz(parse_date(obj_nbf))
    except Exception as e:
        raise DatasourceInvalid("invalid 'gyldigEtter' field: %s (%r)"
                                % (e, obj_nbf))


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


class EmployeeDatasource(AbstractDatasource):

    def __init__(self, client):
        self.client = client

    def get_reference(self, event):
        """ Extract reference from message body """
        return parse_message(event.body)['id']

    def get_object(self, reference):
        """ Fetch data from sap (employee data, assignments, roles). """
        employee_id = reference
        employee_data = self.client.get_employee(employee_id)
        employee = {
            'id': int(reference),
            'employee': {},
            'assignments': {},
        }

        if employee_data:
            employee_data = employee_data[0]
            employee['employee'] = Person('dfo-sap', reference, employee_data)
            assignment_ids = [employee_data['stillingId']]
            for secondary_assignment in assert_list(
                    employee.get('tilleggsstilling')):
                assignment_ids.append(secondary_assignment['stillingId'])

            for assignment_id in assignment_ids:
                assignment = self.client.get_stilling(assignment_id)
                if assignment:
                    employee['assignments'][assignment_id] = (
                        Assignment('dfo-sap', assignment_id, assignment)
                    )
                else:
                    raise DatasourceInvalid('No assignment found: %r' %
                                            assignment_id)

        return Employee('dfo-sap', reference, employee)

    def needs_delay(self, event):
        nbf = parse_message(event.body)['nbf']
        # TODO: return as-is rather than as a timestamp
        if nbf and nbf > now():
            return float(nbf.strftime("%s"))
        return None
