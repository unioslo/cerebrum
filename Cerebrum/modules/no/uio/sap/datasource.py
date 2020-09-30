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
import time
import re
import json
import logging

from Cerebrum.modules.hr_import import datasource as _base

logger = logging.getLogger(__name__)


SUB_2_HR_ID = re.compile(r'employees\((\d+)\)')


def parse_date(value, format='%Y-%m-%d', ignore_error=False):
    if value:
        try:
            return datetime.datetime.strptime(value, format).date()
        except ValueError:
            if ignore_error:
                return None
            else:
                raise
    else:
        return None


def extract_reference(text):
    """ Extract employee reference from a json encoded message body. """
    message = json.loads(text)
    subject = message['sub']
    match = SUB_2_HR_ID.search(subject)
    if not match:
        raise ValueError('Invalid employee reference in sub')
    return match.group(1)


class Employee(_base.RemoteObject):
    pass


class Assignment(_base.RemoteObject):
    pass


class Role(_base.RemoteObject):
    pass


class EmployeeDatasource(_base.AbstractDatasource):

    def __init__(self, client):
        self.client = client

    def get_reference(self, body):
        """ Extract employee reference from a json encoded message body. """
        subject = body['sub']
        match = SUB_2_HR_ID.search(subject)
        if not match:
            raise ValueError('Invalid employee reference in sub')
        return match.group(1)

    def get_object(self, reference):
        """ Fetch data from sap (employee data, assignments, roles). """
        # TODO: Use client to fetch all relevant data, pack into HR objects
        employee_id = reference
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
                for d in self.client.get_assignments(employee)]
            employee['roles'] = [
                Role('sapuio', d['roleId'], d)
                for d in self.client.get_roles(employee)]
        return employee

    def needs_delay(self, body):
        not_before_time = body.get('nbf')  # Example "nbf":1593561600
        if not_before_time:
            if time.time() < not_before_time:
                # TODO:
                #  This is a bit hairy. We may not need to reschedule this if
                #  tiny_scheduler is already listening to the same queue?
                return not_before_time
        return False
