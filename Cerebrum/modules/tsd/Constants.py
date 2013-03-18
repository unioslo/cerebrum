#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2013 University of Oslo, Norway
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
"""Constants specific to the TSD project.

The Constants class defines a set of methods that should be used to
get the actual database code/code_str representing a given Entity,
Address, Gender etc. type.

The TSD project should have their own, minimal set of Constants.

"""

from Cerebrum import Constants
from Cerebrum.Constants import _SpreadCode
from Cerebrum.Constants import _PersonAffiliationCode
from Cerebrum.Constants import _PersonAffStatusCode
from Cerebrum.Constants import _EntityExternalIdCode
from Cerebrum.Constants import _QuarantineCode
from Cerebrum.Constants import _AuthoritativeSystemCode
from Cerebrum.Constants import _AuthenticationCode

class Constants(Constants.Constants):
    ## Affiliations and statuses

    # Project
    affiliation_project = _PersonAffiliationCode('PROJECT',
                                                 'Member of a project')
    # Project Administrator (PA)
    affiliation_status_project_admin = _PersonAffStatusCode(
            affiliation_project, 'admin', 'Project Administrator (PA)')
    # Project Member (PM)
    affiliation_status_project_member = _PersonAffStatusCode(
            affiliation_project, 'member', 'Project Member (PM)')

    ## Spreads

    # AD
    spread_ad_account = _SpreadCode(
        'account@ad', Constants.Constants.entity_account,
        'Account should be synced with AD')

    spread_ad_group = _SpreadCode(
        'group@ad', Constants.Constants.entity_group,
        'Group should be synced with AD')

    spread_gateway_account = _SpreadCode(
        'account@gw', Constants.Constants.entity_account,
        'Account to be synced to the gateway')

    spread_gateway_group = _SpreadCode(
        'group@gw', Constants.Constants.entity_group,
        'Group to be synced to the gateway')

    ## Quarantines

    quarantine_not_approved = _QuarantineCode('not_approved',
                                'Waiting for approval from admin')
    quarantine_project_end = _QuarantineCode('project_end',
                                'Blocking projects when end date is reached')
    quarantine_project_start = _QuarantineCode('not_started_yet',
                          "Project haven't started yet, waiting for start date")

    ## Source systems

    system_nettskjema = _AuthoritativeSystemCode('Nettskjema',
                            'Information from Nettskjema, registered by anyone')
    
    ## Authentication codes (password types):

    auth_type_otp_key = _AuthenticationCode('OTP-key',
            'One-Time Password key, used to be able to generate one-time'
            'passwords')



