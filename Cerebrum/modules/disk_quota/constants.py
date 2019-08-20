# -*- coding: utf-8 -*-
#
# Copyright 2019 University of Oslo, Norway
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
Constants for mod_disk_quota

"""
import Cerebrum.Constants
from Cerebrum.modules.EntityTraitConstants import _EntityTraitCode


class Constants(Cerebrum.Constants.Constants):

    #
    # Traits
    #
    # TBD: These may fit better into mod_disk_quota as actual mixin
    # tables for disk_info and host_info
    trait_host_disk_quota = _EntityTraitCode(
        'host_disk_quota',
        Cerebrum.Constants.Constants.entity_host,
        "The default quota each user gets for disks on this host, "
        "stored in numval."
    )

    trait_disk_quota = _EntityTraitCode(
        'disk_quota',
        Cerebrum.Constants.Constants.entity_disk,
        "The existence of this trait means this disk has quota. "
        "numval contains the default quota.  If it is NULL, the default "
        "quota value is taken from the host_disk_quota trait."
    )


class CLConstants(Cerebrum.Constants.CLConstants):
    """
    Changelog-constants for altering disk_quota
    """

    disk_quota_set = Cerebrum.Constants._ChangeTypeCode(
        'disk_quota',
        'set',
        'set disk quota for %(subject)s',
        (
            'quota=%(int:quota)s',
            'override_quota=%(int:override_quota)s',
            'override_exp=%(string:override_expiration)s',
            'reason=%(string:description)s',
        )
    )

    disk_quota_clear = Cerebrum.Constants._ChangeTypeCode(
        'disk_quota',
        'clear',
        'clear disk quota for %(subject)s'
    )
