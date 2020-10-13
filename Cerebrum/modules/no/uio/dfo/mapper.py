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
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uio.hr_import.models import HRPerson
from Cerebrum.modules.no.uio.hr_import.leader_groups import get_leader_group
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
        return []

    # TODO:
    #  DFØ-SAP will probably fix naming of
    #  organisasjonsId/organisasjonId/orgenhet, so that they are equal at
    #  some point.
    return [main_assignment['orgenhet']]


class EmployeeMapper(_base.EmployeeMapper):
    """A simple employee mapper class"""

    def parse_leader_groups(self, person_data, main_assignment,
                            stedkode_cache):
        """
        Parse leader groups from SAP assignment data

        :param person_data: Data from DFØ-SAP
                            `/ansatte/{id}`
        :type person_data: dict
        :param main_assignment: Assignment data from DFØ-SAP
        :type main_assignment: dict

        :rtype: set(int)
        :return: leader group ids where the person should be a member
        """
        leader_dfo_ou_ids = parse_leader_ous(person_data, main_assignment)

        leader_group_ids = set()
        for dfo_ou_id in leader_dfo_ou_ids:
            stedkode = stedkode_cache.get(dfo_ou_id)
            if stedkode:
                leader_group_ids.add(get_leader_group(self.db,
                                                      stedkode).entity_id)
            else:
                logger.warning('No matching stedkode for OU: %r', dfo_ou_id)

        logger.info('parsed %i leader groups', len(leader_group_ids))
        return leader_group_ids

    def cache_stedkoder(self, assignment_data):
        # TODO:
        #  Remove this once orgreg is ready
        cache = {}
        ou = Factory.get('OU')(self.db)
        co = Factory.get('Constants')(self.db)
        dfo_ou_ids = (a['orgenhet'] for a in assignment_data.values())
        for dfo_ou_id in dfo_ou_ids:
            ou.clear()
            try:
                # TODO:
                #  DFØ-SAP currently uses a mix of int and str for their ids.
                #  This is also falsely documented, so we will have to clean up
                #  the code on our side once DFØ clean up their mess.
                ou.find_by_external_id(co.externalid_dfo_ou_id, str(dfo_ou_id))
            except Errors.NotFoundError:
                logger.warning('OU not found in Cerebrum %r', dfo_ou_id)
            else:
                cache[dfo_ou_id] = ou.get_stedkode()
        return cache

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
        stedkode_cache = self.cache_stedkoder(assignment_data)
        main_assignment = get_main_assignment(person_data, assignment_data)
        hr_person.leader_groups = self.parse_leader_groups(person_data,
                                                           main_assignment,
                                                           stedkode_cache)
