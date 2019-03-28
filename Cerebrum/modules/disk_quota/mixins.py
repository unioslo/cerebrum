# -*- coding: utf-8 -*-
# Copyright 2005-2019 University of Oslo, Norway
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
from Cerebrum import Disk
from Cerebrum import Errors
from Cerebrum.modules.EntityTrait import EntityTrait
from .constants import Constants as _Co


def get_default_host_quota(db, host_id):
    """
    Get default disk quota from host trait.

    :rtype: int
    :return:
        Returns the default disk quota set on the host, or None if no default
        quota is set.
    """
    et = EntityTrait(db)
    try:
        et.find(host_id)
        trait = et.get_trait(_Co.trait_host_disk_quota)
    except Errors.NotFoundError:
        trait = None
    trait = trait or {}
    return trait.get('numval')


def get_default_disk_quota(db, disk_id):
    """
    Get default disk quota from disk trait.

    :rtype: int
    :return:
        Returns the default disk quota set on the host, or None if no default
        quota is set.
    """
    et = EntityTrait(db)
    try:
        et.find(disk_id)
    except Errors.NotFoundError:
        trait = None
    else:
        trait = et.get_trait(_Co.trait_disk_quota)
    trait = trait or {}
    return trait.get('numval')


def has_disk_quota(db, disk_id):
    """
    Check if disk has disk quotas enabled.

    Quotas are enabled/disabled by setting a disk quota trait on the disk.
    The trait may have no default disk quota.

    :rtype: bool
    :return:
        True if quota is enabled.
    """
    et = EntityTrait(db)
    try:
        et.find(disk_id)
    except Errors.NotFoundError:
        trait = None
    else:
        trait = et.get_trait(_Co.trait_disk_quota)
    return trait is not None


class DiskQuotaMixin(Disk.Disk):
    """
    Disk mixin that provides default disk quotas from traits.
    """

    def has_quota(self):
        return has_disk_quota(self._db, self.entity_id)

    def get_default_quota(self):
        """
        Returns the quota, False if the disk has no quotas, or
        None if the disk has quota, but no default quota.
        """
        disk_quota = get_default_disk_quota(self._db, self.entity_id)
        if disk_quota is not None:
            return int(disk_quota)

        host_quota = get_default_host_quota(self._db, self.host_id)
        if host_quota is not None:
            return int(host_quota)

        return None
