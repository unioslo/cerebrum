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
SAPUiO datasource for HR imports.
"""
import datetime
import re
import json
import logging

import six

from Cerebrum.modules.hr_import.datasource import (
    AbstractDatasource,
    DatasourceInvalid,
    RemoteObject,
)
from Cerebrum.utils.date import apply_timezone

logger = logging.getLogger(__name__)


RE_SUBJECT = re.compile(r'employees\((\d+)\)')


def _get_sub(d):
    """ parse 'sub' field from message dict. """
    if 'sub' not in d:
        raise DatasourceInvalid("missing 'sub' field")
    match = RE_SUBJECT.search(d['sub'])
    if not match:
        raise DatasourceInvalid("invalid 'sub' field (%r)" % (d['sub'],))
    return match.group(1)


def _get_jti(d):
    """ parse 'jti' field from message dict. """
    if 'jti' not in d:
        raise DatasourceInvalid("missing 'jti' field")
    return str(d['jti'])


def _get_nbf(d):
    """ parse 'nbf' field from message dict """
    nbf_timestamp = d.get('nbf')
    if not nbf_timestamp:
        return None

    try:
        return apply_timezone(
            datetime.datetime.fromtimestamp(float(nbf_timestamp)))
    except Exception as e:
        raise DatasourceInvalid("invalid 'nbf' field (%r): %s" %
                                (nbf_timestamp, e))


def parse_message(msg_text):
    """ Parse SAPUiO message.

    :param str msg_text: json encoded message

    :rtype: dict
    :return:
        Returns a dict with message fields:

        - id (str): object id
        - nbf (datetime): not before (or None if not given)
    """
    try:
        msg_data = json.loads(msg_text)
    except Exception as e:
        raise DatasourceInvalid('invalid message format: %s (%r)' %
                                (e, msg_text))

    return {
        'id': _get_sub(msg_data),
        'nbf': _get_nbf(msg_data),
        'jti': _get_jti(msg_data),
    }


class Employee(RemoteObject):
    pass


class Assignment(RemoteObject):
    pass


class Role(RemoteObject):
    pass


class EmployeeDatasource(AbstractDatasource):

    def __init__(self, client):
        self.client = client

    def get_reference(self, event):
        """ Extract employee reference from a json encoded message body. """
        return parse_message(event.body)['id']

    def get_object(self, reference):
        """ Fetch data from sap (employee data, assignments, roles). """
        # TODO: Use client to fetch all relevant data, pack into HR objects
        employee_id = six.text_type(reference)
        employee = self.client.get_employee(employee_id)
        if employee is None:
            employee = Employee(
                'sapuio',
                reference,
                {
                    "personId": int(reference),
                    "personnelNumber": reference,
                    "assignments": [],
                    "roles": [],
                }
            )
        else:
            employee['assignments'] = [
                Assignment('sapuio', d['assignmentId'], d)
                for d in self.client.get_assignments(employee_id)]
            employee['roles'] = [
                Role('sapuio', d['roleId'], d)
                for d in self.client.get_roles(employee_id)]
        return employee
