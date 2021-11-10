#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2021 University of Oslo, Norway
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
This module contains utils for secondary sysadm accounts.

A sysadm account is a *personal account* tagged with a specific sysadm-trait
('sysadm_account').  These accounts are handled differently than other
accounts:

- Persons with a sysadm account typically has another *employee* user account
  (referenced by the trait).
- Placed in a separate LDAP tree for Feide
- Persons with sysadm accounts typically has extra protections in place (e.g.
  cannot change password using only an SMS code, but must authenticate using
  IDPorten)
- Sysadm accounts do not have their own email account/inbox, but *do* have a
  forwarding address <uid>@uio.no that forwards to the employee account email
  account (<employee-uid>@uio.no).

Sysadm accounts are created manually using a bofh command (user create_sysadm).
"""
import logging
from Cerebrum.Utils import Factory

logger = logging.getLogger(__name__)


SYSADM_SUFFIX_DRIFT = 'drift'
SYSADM_SUFFIX_NULL = 'null'
SYSADM_SUFFIX_ADM = 'adm'

VALID_SYSADM_SUFFIXES = (
    SYSADM_SUFFIX_DRIFT,
    SYSADM_SUFFIX_NULL,
    SYSADM_SUFFIX_ADM,
)


def get_sysadm_accounts(db, suffix=SYSADM_SUFFIX_DRIFT):
    """
    Fetch sysadm accounts.

    :param db:
        Cerebrum.database object/db connection
    """
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)

    if suffix:
        if suffix not in VALID_SYSADM_SUFFIXES:
            raise ValueError('invalid suffix: ' + repr(suffix))
        name_pattern = '*-{}'.format(suffix)
    else:
        name_pattern = None

    # find all tagged sysadm accounts
    trait = co.trait_sysadm_account
    sysadm_filter = set(t['entity_id'] for t in ac.list_traits(code=trait))
    logger.debug('found %d accounts tagged with trait=%s',
                 len(sysadm_filter), co.trait_sysadm_account)

    # filter acocunt list by personal accounts with name *-drift
    sysadm_accounts = {
        r['account_id']: r
        for r in ac.search(name=name_pattern,
                           owner_type=co.entity_person)
        if r['account_id'] in sysadm_filter
    }
    logger.debug('found %d sysadm accounts (suffix=%s)', len(sysadm_accounts),
                 suffix)

    # identify highest prioritized account/person
    # NOTE: We *really* need to figure out how to use account priority
    #       correctly.  This will pick the highest prioritized *non-expired*
    #       account - which means that the primary account value *will* change
    #       without any user interaction.
    primary_account = {}
    primary_sysadm = {}
    for row in ac.list_accounts_by_type(filter_expired=True,
                                        primary_only=False):
        person_id = row['person_id']
        priority = row['priority']

        # cache primary account (for email)
        if (person_id not in primary_account or
                priority < primary_account[person_id]['priority']):
            primary_account[person_id] = dict(row)

        if row['account_id'] not in sysadm_accounts:
            # non-sysadm account
            continue

        # cache primary sysadm account
        if (person_id not in primary_sysadm or
                priority < primary_sysadm[person_id]['priority']):
            primary_sysadm[person_id] = dict(row)

    logger.info('found %d persons with sysadm accounts', len(primary_sysadm))

    for person_id in primary_sysadm:
        account_id = primary_sysadm[person_id]['account_id']
        account = sysadm_accounts[account_id]

        yield {
            # required by OrgLDIF.list_persons()
            'account_id': account_id,
            'account_name': account['name'],
            'person_id': account['owner_id'],
            'ou_id': primary_sysadm[person_id]['ou_id'],

            # required by SysAdminOrgLdif.list_persons()
            'primary_account_id': primary_account[person_id]['account_id'],
        }
