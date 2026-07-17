# -*- coding: utf-8 -*-
#
# Copyright 2012-2025 University of Oslo, Norway
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
AD sync related constants.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
from Cerebrum import Constants

from Cerebrum.modules.EntityTrait import _EntityTraitCode


class AdSyncConstants(Constants.Constants):
    """
    Constants for the Active Directory sync module, including the basic set of
    AD-attributes that we can manage.
    """
    # Source system for data fetched from AD
    system_ad = Constants._AuthoritativeSystemCode(
        "AD",
        "Information from Active Directory",
    )

    # Active Directory Security ID (SID) external ids
    externalid_groupsid = Constants._EntityExternalIdCode(
        "AD_GRPSID",
        Constants.Constants.entity_group,
        "Group's SID, fetched from Active Directory",
    )
    externalid_accountsid = Constants._EntityExternalIdCode(
        "AD_ACCSID",
        Constants.Constants.entity_account,
        "Account's SID, fetched from Active Directory",
    )

    # Exchange Mailbox Database
    trait_exchange_mdb = _EntityTraitCode(
        "exchange_mdb",
        Constants.Constants.entity_account,
        "The assigned mailbox-database in Exchange for the given account.",
    )
