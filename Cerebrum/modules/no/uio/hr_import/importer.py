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
UIO import.
"""
from Cerebrum.modules.hr_import.employee_import import EmployeeImportBase

from leader_groups import LeaderGroupUpdater
from reservation_group import ReservationGroupUpdater
from account_type import AccountTypeUpdater


class EmployeeImport(EmployeeImportBase):
    """
    An employee import for SAPUiO @ UiO.
    """

    def update(self, hr_object, db_object):
        account_types = AccountTypeUpdater(
            self.db,
            restrict_affiliation=self.const.affiliation_ansatt,
            restrict_source=self.mapper.source_system)

        def _get_affiliations():
            return set(
                (r['affiliation'], r['status'], r['ou_id'])
                for r in db_object.list_affiliations(
                    person_id=db_object.entity_id,
                    affiliation=account_types.restrict_affiliation,
                    source_system=account_types.restrict_source))

        affs_before = _get_affiliations()
        super(EmployeeImport, self).update(hr_object, db_object)
        affs_after = _get_affiliations()

        if affs_before != affs_after:
            account_types.sync(db_object,
                               added=affs_after - affs_before,
                               removed=affs_before - affs_after)

        reservation_group = ReservationGroupUpdater(self.db)
        reservation_group.set(db_object.entity_id, hr_object.reserved)

        leader_groups = LeaderGroupUpdater(self.db)
        leader_groups.sync(db_object.entity_id, hr_object.leader_groups)
