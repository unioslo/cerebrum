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
  account (<employee-uid>@ulrik.uio.no).

Sysadm accounts are created manually using a bofh command (user create_sysadm).
"""
import logging

import six

import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.Errors import NotFoundError, TooManyRowsError
from Cerebrum.modules import Email

logger = logging.getLogger(__name__)


SYSADM_SUFFIX_DRIFT = 'drift'
SYSADM_SUFFIX_NULL = 'null'
SYSADM_SUFFIX_ADM = 'adm'

VALID_SYSADM_SUFFIXES = (
    SYSADM_SUFFIX_DRIFT,
    SYSADM_SUFFIX_NULL,
    SYSADM_SUFFIX_ADM,
)

SYSADM_DEFAULT_EMAIL_DOMAIN = 'uio.no'
SYSADM_EMAIL_DOMAINS = tuple(cereconf.EMAIL_DEFAULT_DOMAINS)


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

    # filter account list by personal accounts with name *-drift
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


def cache_primary_addresses(db, target_type):
    et = Email.EmailTarget(db)
    ed = Email.EmailDomain(db)

    def _iter_addrs():
        for row in et.list_email_target_primary_addresses(
                target_type=target_type):
            if row['target_entity_id'] is None:
                continue
            yield (
                row['target_entity_id'],
                '{}@{}'.format(row['local_part'],
                               ed.rewrite_special_domains(row['domain'])),
            )

    return dict(_iter_addrs())


#
# Sysadm create and utils
#

def create_sysadm_account(db, target_account, suffix, creator_id):
    """
    Create a sysadm account, with a given account as its target.

    :raises ValueError:
        If sysadm cannot be created for the given account, using the given
        suffix
    """
    if suffix not in VALID_SYSADM_SUFFIXES:
        raise ValueError('Invalid sysadm suffix: ' + repr(suffix))

    sysadm_account = Factory.get('Account')(db)
    const = sysadm_account.const

    sysadm_name = '{}-{}'.format(target_account.account_name, suffix)
    if not sysadm_account.validate_new_uname(const.account_namespace,
                                             sysadm_name):
        raise ValueError("account name already in use")
    if not sysadm_account.validate_new_uname(const.group_namespace,
                                             sysadm_name):
        raise ValueError("account name in use by group")

    # Check the target account owner, and look up required info
    if target_account.owner_type != const.entity_person:
        raise ValueError("target account must be a personal account")
    owner = Factory.get('Person')(db)
    owner.find(target_account.owner_id)
    forward_to = get_forward_to_address(target_account)

    # Create basic account object
    sysadm_account.populate(name=sysadm_name,
                            owner_type=owner.entity_type,
                            owner_id=owner.entity_id,
                            np_type=None,
                            creator_id=creator_id,
                            expire_date=None)
    sysadm_account.write_db()
    logger.info('created sysadm account %s (%d) for owner_id %d',
                sysadm_name, sysadm_account.entity_id, owner.entity_id)

    # Tag account with sysadm trait
    sysadm_account.populate_trait(code=const.trait_sysadm_account,
                                  target_id=int(target_account.entity_id))
    sysadm_account.write_db()
    logger.info('tagged sysadm account %s (%d) with %s, target_id=%d',
                sysadm_name, sysadm_account.entity_id,
                const.trait_sysadm_account, target_account.entity_id)

    # Add posix attrs
    # Note: this use of populate() won't work without the PosixUserUiOMixin
    pu = Factory.get('PosixUser')(db)
    pu.populate(pu.get_free_uid(), None, None,
                shell=const.posix_shell_bash, parent=sysadm_account,
                # creator_id is needed as populate() may have to create a new
                # filegroup to use as gid_id
                creator_id=creator_id)
    pu.write_db()
    default_home_spread = const.Spread(cereconf.DEFAULT_HOME_SPREAD)
    pu.add_spread(int(default_home_spread))

    homedir_id = pu.set_homedir(home='/', status=const.home_status_not_created)
    pu.set_home(default_home_spread, homedir_id)
    pu.write_db()
    logger.info('posix promote sysadm account %s (%d), uid=%d',
                sysadm_name, sysadm_account.entity_id, pu.posix_uid)

    # add other defaults
    sysadm_account.add_spread(const.spread_uio_ad_account)

    if suffix == SYSADM_SUFFIX_DRIFT:
        # create email forward
        target = create_forward_target(sysadm_account)
        ensure_forward(target, forward_to)
    else:
        sysadm_account.add_contact_info(const.system_manual,
                                        type=const.contact_email,
                                        value=forward_to)
        sysadm_account.write_db()

    return sysadm_account


def is_sysadm_account(account):
    try:
        primary_account, suffix = account.account_name.split("-")
    except ValueError:
        return False

    if not suffix:
        return False

    if suffix not in VALID_SYSADM_SUFFIXES:
        return False

    if account.const.trait_sysadm_account not in account.get_traits():
        return False

    return True


def get_forward_to_address(target_account):
    """ Get formatted email address for a given target account. """
    db = target_account._db
    et = Email.EmailTarget(db)
    ed = Email.EmailDomain(db)

    try:
        et.find_by_target_entity(int(target_account.entity_id))
    except NotFoundError:
        pass
    else:
        preferred = '{}@ulrik.uio.no'.format(target_account.account_name)
        if preferred in set(
                '{}@{}'.format(r['local_part'],
                               ed.rewrite_special_domains(r['domain']))
                for r in et.get_addresses()):
            return preferred

    # this *shoudn't* happen, but the account is missing a <uid>@ulrik.uio.no
    # fall back to the primary email address
    return target_account.get_primary_mailaddress()


def get_domain_by_name(db, domain_name):
    """ get email domain by domain name. """
    ed = Email.EmailDomain(db)
    ed.find_by_domain(domain_name)
    return ed


def set_default_spam_settings(target):
    """ set default spam settings for new email targets. """
    db = target._db
    const = target.const
    setting = six.text_type(const.EmailTarget(target.email_target_type))

    spam = getattr(cereconf, 'EMAIL_DEFAULT_SPAM_SETTINGS', {}).get(setting)
    if spam:
        spam_level, spam_action = (
            int(const.EmailSpamLevel(spam[0])),
            int(const.EmailSpamAction(spam[1])))
        esf = Email.EmailSpamFilter(db)
        esf.populate(spam_level, spam_action, parent=target)
        esf.write_db()

    filter_ = getattr(cereconf, 'EMAIL_DEFAULT_FILTER', {}).get(setting)
    if filter_:
        etf = Email.EmailTargetFilter(db)
        etf.populate(int(const.EmailTargetFilter(filter_)), parent=target)
        etf.write_db()


def create_forward_target(account):
    """
    Create a EmailTarget of type forward for a given sysadm account.
    """
    db = account._db
    const = account.const
    target = Email.EmailTarget(db)
    localpart = account.account_name

    # Sanity checks
    if SYSADM_DEFAULT_EMAIL_DOMAIN not in SYSADM_EMAIL_DOMAINS:
        raise RuntimeError('Invalid config: SYSADM_DEFAULT_EMAIL_DOMAIN not '
                           'a valid SYSADM_EMAIL_DOMAINS')
    try:
        target.find_by_target_entity(int(account.entity_id))
        raise TooManyRowsError('account already has an email target!')
    except NotFoundError:
        target.clear()

    # create a new, bound forward target with default spam and filter settings
    target.populate(const.email_target_forward,
                    target_entity_id=account.entity_id,
                    target_entity_type=account.entity_type)
    target.write_db()
    set_default_spam_settings(target)

    logger.info('created new forward target %d', target.entity_id)

    # Assign email addresses (uid@<default email domains>)
    primary_id = None
    primary_addr = None
    for domain_name in SYSADM_EMAIL_DOMAINS:
        ed = get_domain_by_name(db, domain_name)
        ea = Email.EmailAddress(db)
        addr = '{}@{}'.format(localpart, ed.email_domain_name)
        try:
            ea.find_by_local_part_and_domain(localpart,
                                             ed.entity_id)
            raise TooManyRowsError('email address taken: ' + repr(addr))
        except NotFoundError:
            ea.clear()
            ea.populate(localpart, ed.entity_id, target.entity_id)
            ea.write_db()
            logger.info('added address %s to target_id=%d',
                        addr, ea.email_addr_target_id)
            if domain_name == SYSADM_DEFAULT_EMAIL_DOMAIN:
                primary_id = ea.entity_id
                primary_addr = addr

    # set primary address
    epa = Email.EmailPrimaryAddressTarget(db)
    epa.populate(int(primary_id), parent=target)
    epa.write_db()
    logger.info('set address %s as primary for target_id=%d',
                primary_addr, target.entity_id)

    return target


def ensure_forward(email_target, forward_address):
    """ Ensure email target has a given forward_to address. """
    # setup forwarding address
    fw = Email.EmailForward(email_target._db)
    fw.find(email_target.entity_id)
    current_forwards = {r['forward_to']: r['enable'] == 'T'
                        for r in fw.get_forward()}

    if forward_address in current_forwards:
        # forward_to exists, but we may have to enable it
        if current_forwards[forward_address]:
            logger.debug('forward to %s already enabled', forward_address)
        else:
            fw.enable_forward(forward_address)
            logger.info('forward to %s enabled', forward_address)
    elif current_forwards and any(current_forwards.values()):
        logger.warning('other, enabled forwards already exists: %s',
                       repr(current_forwards))
    else:
        fw.add_forward(forward_address)
        logger.info('forward to %s added', repr(forward_address))
