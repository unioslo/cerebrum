# -*- coding: utf-8 -*-
#
# Copyright 2006-2018 University of Oslo, Norway
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
"""Access to Cerebrum code values.

The Constants class defines a set of methods that should be used to
get the actual database code/code_str representing a given Entity,
Address, Gender etc. type."""
from __future__ import unicode_literals

from Cerebrum import Constants
from Cerebrum.Constants import (
    _SpreadCode,
    _EntityExternalIdCode,
    _PersonAffiliationCode,
    _PersonAffStatusCode,
)


class Constants(Constants.Constants):

    # affiliation tilknyttet
    affiliation_tilknyttet = _PersonAffiliationCode(
        'TILKNYTTET',
        'Assosiert, reg. i kildesystem')
    # affiliation for FI
    affiliation_status_tilknyttet_fi = _PersonAffStatusCode(
        affiliation_tilknyttet,
        'fi',
        'Manuelt registrert, forsvarsinst.')
    # affiliation for pensjonister
    affiliation_status_tilknyttet_pensjonist = _PersonAffStatusCode(
        affiliation_tilknyttet,
        'pensjonist',
        'Manuelt registrert, pensjonist.')
    # affiliation for park og idrett
    affiliation_status_tilknyttet_park = _PersonAffStatusCode(
        affiliation_tilknyttet,
        'park-idrett',
        'Manuelt registrert, park og idrett.')
    # Spread definitions - user related
    spread_ad_account = _SpreadCode(
        'account@ad', Constants.Constants.entity_account,
        'Brukeren kjent i AD ved NiH')
    spread_exchange_account = _SpreadCode(
        'account@exchange', Constants.Constants.entity_account,
        'Brukeren kjent i AD ved NiH')

    # Spread definitions - group related
    spread_ad_group = _SpreadCode(
        'group@ad', Constants.Constants.entity_group,
        'Gruppe kjent i AD ved NiH')
    spread_exch_group = _SpreadCode(
        'group@exchange', Constants.Constants.entity_group,
        'Gruppe kjent i Exchange ved NiH')
    spread_lms_group = _SpreadCode(
        'group@lms', Constants.Constants.entity_group,
        'Gruppe kjent i LMSen til NiH')

    # external id's for accounts, fetched from AD
    externalid_adsid = _EntityExternalIdCode(
        'ADSID',
        Constants.Constants.entity_account,
        'SID for account as registered in AD')
    externalid_adguid = _EntityExternalIdCode(
        'ADGUID',
        Constants.Constants.entity_account,
        'GUID for account as registered in AD')
