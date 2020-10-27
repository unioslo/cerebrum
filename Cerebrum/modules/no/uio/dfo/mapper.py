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
Mapper for DFØ-SAP.
"""
from __future__ import unicode_literals

import logging

from Cerebrum.modules.no.dfo import mapper as _base
from Cerebrum.modules.no.uio.hr_import.models import HRPerson
from Cerebrum.modules.no.dfo.utils import parse_date
from Cerebrum.modules.no.dfo.mapper import get_main_assignment

logger = logging.getLogger(__name__)


def parse_leader_ous(person_data, main_assignment):
    """
    Parse leader OUs from DFØ-SAP data

    :param person_data: Data from DFØ-SAP
                        `/ansatte/{id}`
    :type person_data: dict
    :param main_assignment: Assignment data from DFØ-SAP
    :type main_assignment: dict

    :rtype: set(int)
    :return OU ids where the person is a leader
    """
    if not main_assignment or not person_data.get('lederflagg'):
        return set()

    # TODO:
    #  DFØ-SAP will probably fix naming of
    #  organisasjonsId/organisasjonId/orgenhet, so that they are equal at
    #  some point.
    return set([main_assignment['orgenhet']])


class EmployeeMapper(_base.EmployeeMapper):
    """A simple employee mapper class"""

    @staticmethod
    def create_hr_person(obj):
        person_id = obj['id']
        person_data = obj['employee']

        return HRPerson(
            hr_id=person_id,
            first_name=person_data.get('fornavn'),
            last_name=person_data.get('etternavn'),
            birth_date=parse_date(person_data.get('fdato'), allow_empty=True),
            gender=person_data.get('kjonn'),
            # TODO:
            #  There does not seem to be any way to determine this in DFO-SAP
            reserved=False
        )

    def update_hr_person(self, hr_person, obj):
        super(EmployeeMapper, self).update_hr_person(hr_person, obj)
        person_data = obj['employee']
        assignment_data = obj['assignments']

        # TODO:
        #  This should be fetched from orgreg by ``datasource.py`` sometime in
        #  the future.
        main_assignment = get_main_assignment(person_data, assignment_data)
        hr_person.leader_groups = parse_leader_ous(person_data,
                                                   main_assignment)
