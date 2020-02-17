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
from Cerebrum.modules.cim.datasource import CIMDataSource


class CIMDataSourceUiA(CIMDataSource):
    def __init__(self, db, config, logger):
        super(CIMDataSourceUiA, self).__init__(db, config, logger)
        self.eligible_affs = (
            self.co.affiliation_ansatt,
            self.co.affiliation_student,
            self.co.affiliation_tilknyttet,
        )

    def is_eligible(self, person_id):
        return bool(self.pe.list_affiliations(person_id=person_id,
                                              affiliation=self.eligible_affs))
