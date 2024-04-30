# -*- coding: utf-8 -*-
#
# Copyright 2020-2024 University of Oslo, Norway
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
OrgLDIF module for generating a sysadm ldif.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

from Cerebrum.Utils import make_timer
from Cerebrum.modules.feide.ldif_mixins import NorEduAuthnLevelMixin
from Cerebrum.modules.no.OrgLDIF import NorEduSmsAuthnMixin
from Cerebrum.modules.no.OrgLDIF import OrgLdifEntitlementsMixin

from . import sysadm_utils

logger = logging.getLogger(__name__)


class SysAdmOrgLdif(NorEduAuthnLevelMixin,
                    NorEduSmsAuthnMixin,
                    OrgLdifEntitlementsMixin):
    """
    Mixin for exporting system administrator accounts (*-drift).

    This OrgLdif mixin changes primary accounts/filtering to only include
    persons with a sysadm account.
    """

    def list_persons(self):
        """
        List persons decides on which accounts to include.

        We override it with one that returns sysadm users.
        """
        return sysadm_utils.get_sysadm_accounts(
            self.db,
            suffix=sysadm_utils.SYSADM_SUFFIX_DRIFT)

    def init_account_mail(self, use_mail_module):
        if use_mail_module:
            timer = make_timer(logger,
                               "Fetching e-mail forward addresses...")

            # cache all sysadm <uname>@uio.no primary addresses (only forwards)
            self.account_mail = sysadm_utils.cache_primary_addresses(
                self.db, self.const.email_target_forward)

            logger.info('found e-mail address for %d accounts',
                        len(self.account_mail))

            timer("...primary account e-mail addresses done.")
        else:
            self.account_mail = None

    @property
    def person_authn_levels(self):
        """Enforces authn level 3 for all users."""
        # Overrides NorEduAuthnLevelMixin.person_authn_levels to require MFA
        # for all included personal user acocunts.
        if not hasattr(self, '_person_authn_levels'):
            d = self._person_authn_levels = {}
            for person_id in self.persons:
                d[person_id] = [('all', '3')]
        return self._person_authn_levels
