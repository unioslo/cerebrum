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

from Cerebrum.modules.hr_import import datasource as _base

logger = logging.getLogger(__name__)


SUB_2_HR_ID = re.compile(r'employees\((\d+)\)')


def in_date_range(value, start=None, end=None):
    """ Check if a date is in a given range. """
    if start and value < start:
        return False
    if end and value > end:
        return False
    return True


def extract_reference(text):
    """ Extract employee reference from a json encoded message body. """
    message = json.loads(text)
    subject = message['sub']
    match = SUB_2_HR_ID.search(subject)
    if not match:
        raise ValueError('Invalid employee reference in sub')
    return match.group(1)


class EmployeeDatasource(_base.AbstractDatasource):

    start_grace = datetime.timedelta(days=3)

    def __init__(self, client):
        self.client = client

    def get_reference(self, event):
        """ Extract reference from event (sap employee id). """
        try:
            reference = extract_reference(event.body)
            logger.debug('found reference=%r from event=%r',
                         reference, event)
            return reference
        except Exception as e:
            logger.debug('unable to extract reference from event=%r',
                         event, exc_info=True)
            raise _base.DatasourceInvalid('Invalid event format: %s (%r)' %
                                          (e, event.body))

    def get_object(self, reference):
        """ Fetch data from sap (employee data, assignments, roles). """
        # TODO: Use client to fetch all relevant data, pack into HR objects
        employee_id = reference
        employee = self.client.get_employee(employee_id)
        if employee is None:
            employee = {
                "personId": int(reference),
                "personnelNumber": reference,
            }
            assignments = []
            roles = []
        else:
            assignments = self.client.get_assignments(employee)
            roles = self.client.get_roles(employee)
        return (employee, assignments, roles)

    def is_active(self, obj):
        # TODO: Examine affs, start/end
        employee = obj[0]
        return employee.get('employmentStatus') == 'active'

    def needs_delay(self, obj):
        start_cutoff = datetime.date.today() - self.start_grace
        employee = obj[0]

        hiredate = employee.get('hireDate')
        if not hiredate:
            return []

        start = datetime.datetime.strptime(hiredate, '%Y-%m-%d').date
        if in_date_range(start_cutoff, start=start):
            return []
        else:
            # Should retry at the actual cutoff
            return [start_cutoff, start]
