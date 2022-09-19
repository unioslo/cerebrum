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
UIO import

This import mixin adds:

- Aff -> account-type change sync (for simple cases)
- Manager groups sync (adm-leder-<location>)
- Reservation group sync (reservation from online publication)
"""
from Cerebrum.modules.hr_import.employee_import import EmployeeImportBase

from leader_groups import ManagerGroupSync
from reservation_group import ReservationGroupUpdater
from account_type import AccountTypeUpdater


def _get_affiliations(db_object, account_types):
    return set(
        (r['affiliation'], r['status'], r['ou_id'])
        for r in db_object.list_affiliations(
            person_id=db_object.entity_id,
            affiliation=account_types.restrict_affiliation,
            source_system=account_types.restrict_source))


class UioEmployeeImportMixin(EmployeeImportBase):

    def __init__(self, *args, **kwargs):
        super(UioEmployeeImportMixin, self).__init__(*args, **kwargs)

        self._leader_group = ManagerGroupSync(self.db)
        self._reservation_group = ReservationGroupUpdater(self.db)

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
        parent_method = super(UioEmployeeImportMixin, self).update

        # Run parent update(), trace aff changes, and transfer aff changes
        # if applicable
        self._update_account_types(hr_object, db_object, parent_method)

        # Calculate if and where this person is a manager - update groups
        leader_ous = (self._get_ou(ou_id_pairs)
                      for ou_id_pairs in hr_object.leader_ous)
        self._leader_group.sync(db_object.entity_id, leader_ous)

        # Update reservation group if flag is set
        self._reservation_group.set(db_object.entity_id, hr_object.reserved)

    def remove(self, hr_object, db_object):
        parent_method = super(UioEmployeeImportMixin, self).remove

        # Run parent remove(), trace aff changes, and transfer aff changes
        # if applicable
        self._update_account_types(hr_object, db_object, parent_method)

        # Remove all org-manager group memberships
        self._leader_group.sync(db_object.entity_id, set())

        # Remove public catalog reservation
        self._reservation_group.set(db_object.entity_id, False)
