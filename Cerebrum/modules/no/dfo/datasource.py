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

import time
import datetime
import logging

from Cerebrum.modules.hr_import import datasource as _base
from Cerebrum.modules.no.dfo.utils import assert_list, parse_date


logger = logging.getLogger(__name__)


def in_date_range(value, start=None, end=None):
    """ Check if a date is in a given range. """
    if start and value < start:
        return False
    if end and value > end:
        return False
    return True


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
        """ Extract reference from message body """
        try:
            return body['id']
        except KeyError:
            raise _base.DatasourceInvalid('No "id" in body: %r', body)

    def get_object(self, reference):
        """ Fetch data from sap (employee data, assignments, roles). """
        employee_id = reference
        employee = self.client.get_employee(employee_id)

        if employee:
            employee['assignments'] = assignments = {}
            assignment_ids = [employee['stillingId']]
            for secondary_assignment in assert_list(
                    employee.get('tilleggsstilling')):
                assignment_ids.append(secondary_assignment['stillingId'])

            for assignment_id in assignment_ids:
                assignment = self.client.get_stilling(assignment_id)
                if assignment:
                    assignments[assignment_id] = (
                        Assignment('dfo-sap', assignment_id, assignment)
                    )
        else:
            employee = {
                'id': int(reference),
                'assignments': {},
            }

        return Employee('dfo-sap', reference, employee)

    def needs_delay(self, body):
        # TODO:
        #  Is gyldigEtter a date equivalent to nbf?
        date_str = body.get('gyldigEtter')
        if date_str:
            not_before_date = parse_date(date_str, '%Y%m%d')
            if datetime.date.today() < not_before_date:
                return time.mktime(not_before_date.timetuple())
        return False
