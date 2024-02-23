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

CLASS_CONSTANTS = (
    'Cerebrum.modules.no.uio.Constants/Constants',
    'Cerebrum.modules.no.uio.legacy_constants/LegacyConstants',
    'Cerebrum.modules.no.Constants/ConstantsCommon',
    'Cerebrum.modules.exchange.Constants/Constants',
    'Cerebrum.modules.exchange.TargetSystemConstants/TargetSystemConstants',
    'Cerebrum.modules.PosixConstants/Constants',
    'Cerebrum.modules.bofhd.bofhd_constants/Constants',
    'Cerebrum.modules.bofhd_requests.constants/Constants',
    'Cerebrum.modules.EmailConstants/EmailConstants',
    'Cerebrum.modules.no.uio.EphorteConstants/EphorteConstants',
    'Cerebrum.modules.no.dfo.constants/DfoConstants',
    'Cerebrum.modules.orgreg.constants/OrgregConstants',
    'Cerebrum.modules.otp.constants/OtpConstants',
    'Cerebrum.modules.password_notifier.constants/Constants',
    'Cerebrum.modules.guest.Constants/GuestConstants',
    'Cerebrum.modules.consent.ConsentConstants/Constants',
    'Cerebrum.modules.cim.constants/ConstantsMixin',
    'Cerebrum.modules.disk_quota.constants/Constants',
    'Cerebrum.modules.feide.Constants/Constants',
    'Cerebrum.modules.greg.constants/GregConstants',
    'Cerebrum.modules.no.uio.voip.Constants/VoipConstants',
    'Cerebrum.modules.no.uio.voip.Constants/VoipAuthConstants',
    'Cerebrum.modules.EntityTraitConstants/Constants',
)

CLASS_CL_CONSTANTS = (
    'Cerebrum.modules.no.uio.legacy_constants/LegacyChangelogConstants',
    'Cerebrum.modules.otp.constants/OtpChangeTypeConstants',
    'Cerebrum.modules.ou_disk_mapping.constants/CLConstants',
    'Cerebrum.modules.apikeys.constants/CLConstants',
    'Cerebrum.modules.disk_quota.constants/CLConstants',
    'Cerebrum.modules.feide.Constants/CLConstants',
    'Cerebrum.modules.consent.ConsentConstants/CLConstants',
    'Cerebrum.modules.no.uio.EphorteConstants/CLConstants',
    'Cerebrum.modules.EntityTraitConstants/CLConstants',
    'Cerebrum.modules.EmailConstants/CLConstants',
    'Cerebrum.modules.exchange.CLConstants/CLConstants',
    'Cerebrum.modules.ad2.CLConstants/CLConstants',
    'Cerebrum.Constants/CLConstants',
)

CLASS_CHANGELOG = (
    'Cerebrum.modules.event_publisher.eventlog/EventLog',
    'Cerebrum.modules.EventLog/EventLog',
    'Cerebrum.modules.ChangeLog/ChangeLog',
    'Cerebrum.modules.audit.auditlog/AuditLog',
)

CLASS_ENTITY = (
    'Cerebrum.modules.EntityTrait/EntityTrait',
    'Cerebrum.modules.bofhd.bofhd_mixins/BofhdAuthEntityMixin',
)

CLASS_ACCOUNT = (
    'Cerebrum.modules.no.uio.voip.voipAuthAccountMixin/VoipAuthAccountMixin',
    'Cerebrum.modules.no.uio.Account/AccountUiOMixin',
    'Cerebrum.modules.apikeys.mixins/ApiMappingAccountMixin',
    'Cerebrum.modules.pwcheck.history/PasswordHistoryMixin',
    'Cerebrum.modules.AccountExtras/AutoPriorityAccountMixin',
    'Cerebrum.modules.Email/AccountEmailMixin',
    'Cerebrum.modules.Email/AccountEmailQuotaMixin',
    'Cerebrum.modules.gpg.password/AccountPasswordEncrypterMixin',
    'Cerebrum.modules.no.uio.changed_password_notifier/NotifyChangePasswordMixin',  # noqa: E501
)

CLASS_GROUP = (
    'Cerebrum.modules.no.uio.Group/GroupUiOMixin',
    'Cerebrum.modules.posix.mixins/PosixGroupMixin',
    'Cerebrum.modules.exchange.mixins/SecurityGroupMixin',
    'Cerebrum.modules.exchange.mixins/DistributionGroupMixin',
    'Cerebrum.modules.feide.service/FeideServiceAuthnLevelMixin',
    'Cerebrum.Group/Group',
)

CLASS_PERSON = (
    'Cerebrum.modules.otp.mixins/OtpPersonMixin',
    'Cerebrum.modules.Email/PersonEmailMixin',
    'Cerebrum.modules.no.Person/PersonFnrMixin',
    'Cerebrum.modules.consent.Consent/EntityConsentMixin',
    'Cerebrum.modules.feide.service/FeideServiceAuthnLevelMixin',
    'Cerebrum.modules.no.uio.Person/PersonUiOMixin',
)

CLASS_OU = (
    'Cerebrum.modules.ou_disk_mapping.mixins/OUMixin',
    'Cerebrum.modules.no.Stedkode/Stedkode',
)

CLASS_DISK = (
    'Cerebrum.modules.ou_disk_mapping.mixins/DiskMixin',
    'Cerebrum.modules.disk_quota.mixins/DiskQuotaMixin',
)

CLASS_POSIX_USER = (
    'Cerebrum.modules.no.uio.PosixUser/PosixUserUiOMixin',
    'Cerebrum.modules.PosixUser/PosixUser',
)

CLASS_POSIX_GROUP = (
    'Cerebrum.modules.no.uio.PosixGroup/PosixGroupUiOMixin',
    'Cerebrum.modules.PosixGroup/PosixGroup',
)

CLASS_POSIXLDIF = (
    'Cerebrum.modules.otp.otp_ldif_utils/RadiusOtpMixin',
    'Cerebrum.modules.no.uio.PosixLDIF/PosixLDIF_UiOMixin',
    'Cerebrum.modules.PosixLDIF/PosixLDIFRadius',
    'Cerebrum.modules.PosixLDIF/PosixLDIFMail',
    'Cerebrum.modules.PosixLDIF/PosixLDIF',
)
