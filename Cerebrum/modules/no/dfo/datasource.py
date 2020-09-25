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
from __future__ import unicode_literals

"""
SAPUiO datasource for HR imports.
"""

import datetime
import json
import logging

from Cerebrum.modules.hr_import import datasource as _base

logger = logging.getLogger(__name__)


def in_date_range(value, start=None, end=None):
    """ Check if a date is in a given range. """
    if start and value < start:
        return False
    if end and value > end:
        return False
    return True


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
    return message['id']


class Employee(_base.RemoteObject):
    pass


class Assignment(_base.RemoteObject):
    pass


class Role(_base.RemoteObject):
    pass


class EmployeeDatasource(_base.AbstractDatasource):
    # TODO:
    #  Should be config. We also probably don't need to consider this until
    #  after a HRPerson has been constructed. Is it up to the mapper or the
    #  import to decide this?
    start_grace = datetime.timedelta(days=-6)
    end_grace = datetime.timedelta(days=0)

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
            logger.debug('unable to extract reference from event=%r', event)
            raise _base.DatasourceInvalid('Invalid event format: %s (%r)' %
                                          (e, event.body))

    def get_object(self, reference):
        """ Fetch data from sap (employee data, assignments, roles). """
        employee_id = reference
        employee = self.client.get_employee(employee_id)
        assignments = dict()

        if employee:
            assignment_ids = [employee['stillingId']]
            for secondary_assignment in employee.get('tilleggsstilling') or []:
                assignment_ids.append(secondary_assignment['stillingId'])

            for assignment_id in assignment_ids:
                assignment = self.client.get_stilling(assignment_id)
                if assignment:
                    assignments[assignment_id] = (
                        # TODO:
                        #  Handle source, it should be dfosap<inst> or
                        #  something? Is it really necessary?
                        Assignment('sapuio', assignment_id, assignment)
                    )

        return Employee(
                # TODO:
                #  Handle source, it should be dfosap<inst> or something?
                'sapuio',
                reference,
                {
                    "personId": int(reference),
                    "personnelNumber": reference,
                    "assignments": assignments
                }
            )

    # TODO:
    #  Would it maybe be better to handle this further down the line? This is
    #  potentially the same logic for both dfo-sap and sap, so it would be
    #  more general if it was handled after conversion to HRPerson. It should
    #  however be possible to configure per institution.
    # TODO:
    #  Fix it
    def needs_delay(self, obj):
        # t = datetime.date.today()
        # start_cutoff = t + self.start_grace
        # end_cutoff = t + self.end_grace
        #
        # assigns, roles = obj['assignments'], obj['roles']
        #
        # active_date_ranges = []
        #
        # for a in assigns + roles:
        #     active_date_ranges.append(
        #         (parse_date(a.get('effectiveStartDate'), ignore_error=True),
        #          parse_date(a.get('effectiveEndDate'), ignore_error=True))
        #     )
        #
        # retry_dates = []
        #
        # for start, end in active_date_ranges:
        #     if (not in_date_range(start_cutoff, start=start)
        #             and in_date_range(end_cutoff, end=end)):
        #         retry_dates.append(start_cutoff)
        # return retry_dates
        return False
