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
Custom CIM Data Source for UiA

Instead of going the usual path of logic -> CIM spread -> provision we instead
do logic -> provision.

Pros: Eligibility is calculated on the fly
Cons: Admins at UiA can't check a spread to determine if a person should be in
CIM

"""
from __future__ import unicode_literals

from Cerebrum.modules.cim.datasource import CIMDataSource


class CIMDataSourceUiA(CIMDataSource):
    def __init__(self, db, config, logger):
        super(CIMDataSourceUiA, self).__init__(db, config, logger)
        self._eligible_affs = (
            self.co.affiliation_ansatt,
            self.co.affiliation_student,
            self.co.affiliation_tilknyttet,
        )
        self.dist_list_names = {
            'student_grim': 'Student Campus Grimstad',
            'ansatt_grim': 'Ansatt Campus Grimstad',
            'student_kris': 'Student Campus Kristiansand',
            'ansatt_kris': 'Ansatt Campus Kristiansand'}

    def is_eligible(self, person_id):
        return bool(self.pe.list_affiliations(person_id=person_id,
                                              affiliation=self._eligible_affs))

    def create_dist_lists(self, *args, **kwargs):
        """Add extra UiA specific data to the payload

        The distribution lists at UiA are based on the affiliation
        and stedkode of the OU they are affiliated to.

        Anyone with affiliation ANSATT or TILKNYTTET are regarded as
        ansatt, while STUDENT are students. If the stedkode of the
        OU ends in 11 they belong to Campus Kristiansand. If the
        stedkode ends in 40 they belong to Campus Grimstad.

        If we can't match affiliation and stedkode we return None

        :rtype str or None
        :return: distribution list
        """

        if 'primary_aff' in kwargs:
            primary_aff = kwargs['primary_aff']
        else:
            self.logger.warning(
                "No primary aff sent to create_dist_list. Ignoring dist_list "
                "for person %s", self.pe.entity_id)
            return None

        self.ou.clear()
        self.ou.find(primary_aff['ou_id'])
        last_two = self.ou.get_stedkode()[-2:]
        affiliation = primary_aff['affiliation']

        if affiliation == self.co.affiliation_student and last_two == '40':
            dist_list = self.dist_list_names['student_grim']
        elif affiliation in (
                self.co.affiliation_ansatt,
                self.co.affiliation_tilknyttet) and last_two == '40':
            dist_list = self.dist_list_names['ansatt_grim']
        elif affiliation == self.co.affiliation_student and last_two == '11':
            dist_list = self.dist_list_names['student_kris']
        elif affiliation in (
                self.co.affiliation_ansatt,
                self.co.affiliation_tilknyttet) and last_two == '11':
            dist_list = self.dist_list_names['ansatt_kris']
        else:
            dist_list = None
        return dist_list

    def get_person_data(self, person_id):
        person = super(CIMDataSourceUiA, self).get_person_data(person_id)

        # We do not have the data to decide if a person should be a user or
        # a contact. For now we give everyone 'user'. There is a default value
        # in the CIM installation but we choose to not trust that setting. If
        # we decide to use the default we can stop sending the 'person_type'
        # attribute.
        if person:
            person['person_type'] = 'user'
        return person
