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


def _get_affiliations(db_object, account_types):
    return set(
        (r['affiliation'], r['status'], r['ou_id'])
        for r in db_object.list_affiliations(
            person_id=db_object.entity_id,
            affiliation=account_types.restrict_affiliation,
            source_system=account_types.restrict_source))


class EmployeeImport(EmployeeImportBase):
    """
    An employee import for SAP and DFØ @ UiO.
    """

    def _update_account_types(self, hr_object, db_object, parent_method):
        account_types = AccountTypeUpdater(
            self.db,
            restrict_affiliation=self.const.affiliation_ansatt,
            restrict_source=self.source_system)

        affs_before = _get_affiliations(db_object, account_types)
        parent_method(hr_object, db_object)
        affs_after = _get_affiliations(db_object, account_types)

        if affs_before != affs_after:
            account_types.sync(db_object,
                               added=affs_after - affs_before,
                               removed=affs_before - affs_after)

    def update(self, hr_object, db_object):
        parent_method = super(EmployeeImport, self).update
        self._update_account_types(hr_object, db_object, parent_method)

        reservation_group = ReservationGroupUpdater(self.db)
        reservation_group.set(db_object.entity_id, hr_object.reserved)

        leader_groups = LeaderGroupUpdater(self.db, self.source_system)
        leader_groups.sync(db_object.entity_id, hr_object.leader_groups)

    def remove(self, hr_object, db_object):
        parent_method = super(EmployeeImport, self).remove
        self._update_account_types(hr_object, db_object, parent_method)

        reservation_group = ReservationGroupUpdater(self.db)
        reservation_group.set(db_object.entity_id, False)

        leader_groups = LeaderGroupUpdater(self.db, self.source_system)
        leader_groups.sync(db_object.entity_id, set())
