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
"""
from __future__ import unicode_literals

import logging

from Cerebrum.modules.no.dfo import mapper as _base

logger = logging.getLogger(__name__)


def get_main_assignment(employee_data):
    main_id = employee_data.get('stillingId')
    assignments = employee_data.get('assignments') or {}
    return assignments.get(main_id)


def parse_leader_ous(employee_data):
    """
    Parse leader OUs from DFØ-SAP data

    :param dict employee_data: Normalized employee data

    :rtype: set[int]
    :returns: DFØ org unit ids where the person is a leader
    """
    main_assignment = get_main_assignment(employee_data)
    if not main_assignment or not employee_data.get('lederflagg'):
        return set()

    # TODO:
    #  DFØ-SAP will probably fix naming of
    #  organisasjonsId/organisasjonId/orgenhet, so that they are equal at
    #  some point.
    return set([main_assignment['organisasjonId']])


class EmployeeMapper(_base.EmployeeMapper):
    """A simple employee mapper class"""

    def translate(self, reference, employee_data):
        person = super(EmployeeMapper, self).translate(reference,
                                                       employee_data)

        # eksternbruker isn't populated at uio - all active employees should be
        # considered
        person.enable = True

        # set reservation
        setattr(person, 'reserved',
                employee_data.get('reservasjonPublisering'))

        # A list of org units where this person is considered a manager
        # Each org unit is a list of (id_type, id_value) pairs
        ou_terms = [[('DFO_OU_ID', org_id)]
                    for org_id in parse_leader_ous(employee_data)]
        setattr(person, 'leader_ous', ou_terms)
        return person
