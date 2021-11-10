#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
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

TODOs
-----
Non-arbitrary account priority
    We should fix the account priority lookups to avoid 'fallback' to a less
    prioritized account when adding filters (expire_date, spreads).

    The whole account priority bit should probably be separated from
    account_type.

Missing mandatory attrs
    Missing eduPersonPrimaryOrgUnitDN, eduPersonOrgUnitDN.  Not sure how to
    handle:

    1. Dummy OU and set OrgUnit to that?
    2. Refer to OUs at cn=organization,dc=uio,dc=no?  We'd need to somehow
       build the ou-mapping (ou2DN) like OrgLDIF, but without outputting any
       OUs.
    3. These attrs are semi-mandatory, and low availability in higher edu -
       should we just ignore them?
"""
from __future__ import print_function, unicode_literals

import logging

from Cerebrum.Utils import make_timer
from Cerebrum.modules.Email import EmailTarget
from Cerebrum.modules.no.OrgLDIF import norEduLDIFMixin

from . import sysadm_utils

logger = logging.getLogger(__name__)


def _get_feide_sysadm_accounts(db):
    return sysadm_utils.get_sysadm_accounts(
        db,
        suffix=sysadm_utils.SYSADM_SUFFIX_DRIFT)


class SysAdmOrgLdif(norEduLDIFMixin):
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
        self._account_to_primary = pri = {}
        for account in _get_feide_sysadm_accounts(self.db):
            pri[account['account_id']] = account.pop('primary_account_id')
            yield account

    def init_account_mail(self, use_mail_module):
        if use_mail_module:
            timer = make_timer(logger,
                               "Fetching primary account e-mail addresses...")
            # cache all <uname>@uio.no email addresses
            targets = EmailTarget(self.db).list_email_target_addresses
            mail = {}
            for row in targets(target_type=self.const.email_target_account,
                               domain='uio.no', uname_local=True):
                # Can only return username@uio.no so no need for any checks
                mail[int(row['target_entity_id'])] = "@".join(
                    (row['local_part'], row['domain']))

            # Pick an appropriate email address for each account
            self.account_mail = {}
            for account_id, pri_id in self._account_to_primary.items():
                if pri_id in mail:
                    self.account_mail[account_id] = mail[pri_id]
                else:
                    logger.warning('No email address for account_id=%d, '
                                   'primary_account_id=%d', account_id, pri_id)
            logger.info('found e-mail address for %d accounts',
                        len(self.account_mail))

            timer("...primary account e-mail addresses done.")
        else:
            self.account_mail = None

    @property
    def person_authn_levels(self):
        """Enforces authn level 3 for all users."""
        if not hasattr(self, '_person_authn_levels'):
            d = self._person_authn_levels = {}
            for person_id in self.persons:
                d[person_id] = [('all', '3')]
        return self._person_authn_levels
