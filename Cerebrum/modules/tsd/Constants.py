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
from Cerebrum.modules.EntityTrait import _EntityTraitCode


class Constants(Constants.Constants):
    # Affiliations and statuses

    # Project
    affiliation_project = _PersonAffiliationCode('PROJECT',
                                                 'Member of a project')
    # Project Owner
    affiliation_status_project_owner = _PersonAffStatusCode(
        affiliation_project, 'owner', 'Project Owner')
    # Project Administrator (PA)
    affiliation_status_project_admin = _PersonAffStatusCode(
        affiliation_project, 'admin', 'Project Administrator (PA)')
    # Project Member (PM)
    affiliation_status_project_member = _PersonAffStatusCode(
        affiliation_project, 'member', 'Project Member (PM)')

    # Pending
    affiliation_pending = _PersonAffiliationCode('PENDING',
                                                 'Unapproved affiliations')
    # Pending project member (PM)
    affiliation_status_pending_project_member = _PersonAffStatusCode(
        affiliation_pending, 'member',
        'Waiting for getting accepted as a project member')

    # Spreads

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

    # The gateway doesn't care about groups
    # spread_gateway_group = _SpreadCode(
    #    'group@gw', Constants.Constants.entity_group,
    #    'Group to be synced to the gateway')

    # Quarantines

    quarantine_autopassord = _QuarantineCode('autopassord',
                                             'Password out of date')
    quarantine_generell = _QuarantineCode('generell',
                                          'General block')
    quarantine_teppe = _QuarantineCode('teppe',
                                       'Quarantine for severe issues')

    quarantine_not_approved = _QuarantineCode('not_approved',
                                              'Waiting for approval from admin')
    quarantine_project_end = _QuarantineCode('project_end',
                                             'Blocking projects when end date is reached')
    quarantine_project_start = _QuarantineCode('not_started_yet',
                                               "Project haven't started yet, waiting for start date")

    quarantine_frozen = _QuarantineCode('frozen', 'Project is frozen')

    # Source systems
    system_nettskjema = _AuthoritativeSystemCode('Nettskjema',
                                                 'Information from Nettskjema, registered by anyone')
    system_ad = _AuthoritativeSystemCode('AD', 'Information from AD')

    # Traits

    trait_project_group = _EntityTraitCode('project_group',
                                           Constants.Constants.entity_group,
                                           'The project a group belongs to')
    trait_project_host = _EntityTraitCode('project_host',
                                          Constants.Constants.entity_host,
                                          'The project a host belongs to')

    # Traits for metadata about projects:
    trait_project_institution = _EntityTraitCode('institution',
                                                 Constants.Constants.entity_ou,
                                                 'The institution the project belongs to')
    trait_project_rek = _EntityTraitCode('rek_approval',
                                         Constants.Constants.entity_ou,
                                         'The REK approval for the project')

    trait_project_persons_accepted = _EntityTraitCode('accepted_persons',
                                                      Constants.Constants.entity_ou,
                                                      'FNRs of non-existing persons that has been '
                                                      'accepted as members of the project')

    # Authentication codes (password types):

    trait_otp_device = _EntityTraitCode('otp_device',
                                        Constants.Constants.entity_person,
                                        'The device for handling the OTP keys, e.g. yubikey or smartphone')

    auth_type_otp_key = _AuthenticationCode('OTP-key',
                                            'One-Time Password key, used to be able to generate one-time'
                                            'passwords')
