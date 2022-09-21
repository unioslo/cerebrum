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
import logging
from Cerebrum.modules.hr_import.employee_import import EmployeeImportBase

from leader_groups import ManagerGroupSync
from reservation_group import ReservationGroupUpdater
from account_type import AccountTypeUpdater

logger = logging.getLogger(__name__)


def _get_affiliations(db_object, account_types):
    return set(
        (r['affiliation'], r['status'], r['ou_id'])
        for r in db_object.list_affiliations(
            person_id=db_object.entity_id,
            affiliation=account_types.restrict_affiliation,
            source_system=account_types.restrict_source))


class AccountTypeMixin(EmployeeImportBase):
    """
    Import mixin that tries to update account types on affiliation change.
    """

    def __init__(self, *args, **kwargs):
        super(AccountTypeMixin, self).__init__(*args, **kwargs)
        # Account type updater
        self._account_update = AccountTypeUpdater(
            self.db,
            restrict_affiliation=self.const.affiliation_ansatt,
            restrict_source=self.source_system)

    def update(self, hr_object, db_object):
        # Track aff changes in parent.update()
        affs_before = _get_affiliations(db_object, self._account_update)
        super(AccountTypeMixin, self).update(hr_object, db_object)
        affs_after = _get_affiliations(db_object, self._account_update)

        # Try to update account types on change
        if affs_before != affs_after:
            added_affs = affs_after - affs_before
            removed_affs = affs_before - affs_after
            logger.debug('AccountTypeMixin aff changes: added=%s, removed=%s',
                         repr(added_affs), repr(removed_affs))
            self._account_update.sync(db_object, added=added_affs,
                                      removed=removed_affs)

    def remove(self, hr_object, db_object):
        # Track aff changes in parent.remove()
        affs_before = _get_affiliations(db_object, self._account_update)
        super(AccountTypeMixin, self).remove(hr_object, db_object)
        affs_after = _get_affiliations(db_object, self._account_update)

        # Try to update account types on change
        if affs_before != affs_after:
            added_affs = affs_after - affs_before
            removed_affs = affs_before - affs_after
            logger.debug('AccountTypeMixin aff changes: added=%s, removed=%s',
                         repr(added_affs), repr(removed_affs))
            self._account_update.sync(db_object, added=added_affs,
                                      removed=removed_affs)


class ManagerGroupMixin(EmployeeImportBase):
    """
    Import mixin that tries to update manager groups according to a
    `hr_object.leader_ous` attribute.
    """

    def __init__(self, *args, **kwargs):
        super(ManagerGroupMixin, self).__init__(*args, **kwargs)
        # Manager group sync
        self._mgr_groups = ManagerGroupSync(self.db)

    def update(self, hr_object, db_object):
        super(ManagerGroupMixin, self).update(hr_object, db_object)

        # Manager org unit itentifiers
        manager_ou_ids = tuple(hr_object.leader_ous)
        logger.debug('ManagerGroupMixin: manager at ou=%s',
                     repr(manager_ou_ids))

        # Find org units and update
        ou_objects = tuple(self._get_ou(ou_id_pairs)
                           for ou_id_pairs in manager_ou_ids)
        self._mgr_groups.sync(db_object.entity_id, ou_objects)

    def remove(self, hr_object, db_object):
        super(ManagerGroupMixin, self).remove(hr_object, db_object)
        # Remove all org-manager group memberships
        logger.debug('ManagerGroupMixin: removing manager positions')
        self._mgr_groups.sync(db_object.entity_id, set())


class ReservationGroupMixin(EmployeeImportBase):
    """
    Import mixin that tries to update reservation groups according to a
    `hr_object.reserved` attribute.
    """
    def __init__(self, *args, **kwargs):
        super(ReservationGroupMixin, self).__init__(*args, **kwargs)
        # Reservation group sync
        self._reservation_group = ReservationGroupUpdater(self.db)

    def update(self, hr_object, db_object):
        super(ReservationGroupMixin, self).update(hr_object, db_object)
        # Update reservation group if flag is set
        is_reserved = hr_object.reserved
        logger.debug('ReservationGroupMixin: is-reserved=%s',
                     repr(is_reserved))
        self._reservation_group.set(db_object.entity_id, is_reserved)

    def remove(self, hr_object, db_object):
        super(ReservationGroupMixin, self).remove(hr_object, db_object)
        # Remove public catalog reservation
        logger.debug('ReservationGroupMixin: removing reservations')
        self._reservation_group.set(db_object.entity_id, False)


class UioEmployeeImportMixin(AccountTypeMixin, ManagerGroupMixin,
                             ReservationGroupMixin, EmployeeImportBase):
    pass
