#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2018 University of Oslo, Norway
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

from cereconf_test import *

CLASS_CHANGELOG = [
    'Cerebrum.modules.EventLog/EventLog',
    'Cerebrum.modules.ChangeLog/ChangeLog', ]

CLASS_CONSTANTS = [
    'Cerebrum.modules.no.Constants/ConstantsCommon',
    'Cerebrum.modules.no.Constants/ConstantsHigherEdu',
    'Cerebrum.modules.no.uio.Constants/Constants',
    # exchange-relatert-jazz
    'Cerebrum.modules.exchange.Constants/Constants',
    'Cerebrum.modules.exchange.TargetSystemConstants/TargetSystemConstants',
    'Cerebrum.modules.PosixUser/Constants',
    'Cerebrum.modules.Email/CLConstants',
    'Cerebrum.modules.exchange.CLConstants/CLConstants',
    'Cerebrum.modules.ad2.CLConstants/CLConstants',
    'Cerebrum.modules.CLConstants/CLConstants',
    'Cerebrum.modules.bofhd.utils/Constants',
    'Cerebrum.modules.Email/EmailConstants',
    'Cerebrum.modules.EntityTrait/TraitConstants',
    'Cerebrum.modules.AuthPGP/Constants',
    'Cerebrum.modules.no.uio.DiskQuota/DiskQuotaConstants',
    'Cerebrum.modules.no.uio.Ephorte/EphorteConstants',
    'Cerebrum.modules.password_notifier.constants/Constants',
    'Cerebrum.modules.guest.Constants/GuestConstants',
    'Cerebrum.modules.consent.Consent/Constants',
    'Cerebrum.modules.cim.constants/ConstantsMixin',
    'Cerebrum.modules.no.uio.printer_quota.PaidPrinterQuotas/Constants',
    'Cerebrum.modules.no.uio.printer_quota.bofhd_pq_cmds/Constants',
    'Cerebrum.modules.no.uio.voip.Constants/VoipConstants',
    'Cerebrum.modules.no.uio.voip.EntityAuthentication/VoipAuthConstants',
    'Cerebrum.modules.dns.DnsConstants/Constants',
    'Cerebrum.modules.dns.bofhd_dns_cmds/Constants',
    'Cerebrum.modules.hostpolicy.HostPolicyConstants/Constants',
]


CLASS_ENTITY = ['Cerebrum.modules.EntityTrait/EntityTrait',]

CLASS_ACCOUNT = (
    'Cerebrum.modules.no.uio.Account/AccountUiOMixin',
    'Cerebrum.modules.pwcheck.history/PasswordHistoryMixin',
    'Cerebrum.modules.AccountExtras/AutoPriorityAccountMixin',
    'Cerebrum.modules.AuthPGP/AuthPGPAccountMixin',
    'Cerebrum.modules.Email/AccountEmailMixin',
    'Cerebrum.modules.Email/AccountEmailQuotaMixin',
    'Cerebrum.modules.gpg.password/AccountPasswordEncrypterMixin',
)

CLASS_GROUP = (
    'Cerebrum.modules.no.uio.Group/GroupUiOMixin',
    'Cerebrum.modules.posix.mixins/PosixGroupMixin',
    'Cerebrum.modules.exchange.mixins/SecurityGroupMixin',
    'Cerebrum.modules.exchange.mixins/DistributionGroupMixin',
    'Cerebrum.Group/Group',
)

CLASS_OU = ('Cerebrum.modules.no.Stedkode/Stedkode',)
CLASS_DISK = ('Cerebrum.modules.no.uio.Disk/DiskUiOMixin',)
CLASS_PERSON = (
    'Cerebrum.modules.Email/PersonEmailMixin',
    'Cerebrum.modules.no.Person/PersonFnrMixin',
    'Cerebrum.modules.consent.Consent/EntityConsentMixin',
    'Cerebrum.modules.no.uio.Person/PersonUiOMixin'
)
CLASS_POSIX_USER = ('Cerebrum.modules.no.uio.PosixUser/PosixUserUiOMixin',
                    'Cerebrum.modules.PosixUser/PosixUser')
CLASS_POSIXLDIF = ('Cerebrum.modules.no.uio.PosixLDIF/PosixLDIF_UiOMixin',
                   'Cerebrum.modules.PosixLDIF/PosixLDIFRadius',
                   'Cerebrum.modules.PosixLDIF/PosixLDIF')