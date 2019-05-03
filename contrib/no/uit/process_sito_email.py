#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002-2019 University of Oslo, Norway
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
Create or update email addresses for all sito accounts.

This script iterates over all sito accounts with email spreads and asserts that
they have an email address set.

Configuration
-------------
This script use the following cereconf variables:

DEFAULT_LOGGER_TARGET
    The default logger preset to use if no --logger-name is given.

SITO_PRIMARY_MAILDOMAIN
    Which mail domain to assign new email addresses to.

USERNAME_POSTFIX['sito']
    Required account name postfix to be considered a sito account.
"""
from __future__ import absolute_import, print_function

import argparse
import logging

import cereconf
import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.funcwrap import memoize
from Cerebrum.modules.no.uit import Email
from Cerebrum.modules.Email import EmailDomain, EmailAddress
from Cerebrum.utils.argutils import add_commit_args


logger = logging.getLogger(__name__)

sito_domain = getattr(cereconf, 'SITO_PRIMARY_MAILDOMAIN')
sito_postfix = getattr(cereconf, 'USERNAME_POSTFIX', {}).get('sito')


@memoize
def get_domainid(db, domain_part):
    domain = EmailDomain(db)
    domain.find_by_domain(domain_part)
    return domain.entity_id


def is_cnaddr_free_old(db, local_part, domain_part):
    domain_id = get_domainid(db, domain_part)
    ea = EmailAddress(db)
    logger.debug("Considering %s, %s", local_part, domain_part)
    try:
        ea.find_by_local_part_and_domain(local_part, domain_id)
    except Errors.NotFoundError:
        # emailaddress is free.
        logger.debug("Address %s@%s is free", local_part, domain_part)
    else:
        logger.warn("Address %s@%s is not free!", local_part, domain_part)
        return False
    return True


def format_addr(local_part, domain_part):
    return '{}@{}'.format(local_part, domain_part)


class AddressGenerator(object):

    def __init__(self, db):
        self.db = db
        self.in_use = set()
        self.new_addrs = set()

    def get_alternatives(self, account_name):
        ac = Factory.get('Account')(self.db)
        ac.find_by_name(account_name)
        alternatives = list()
        first_choice = ac.get_email_cn_local_part(given_names=1,
                                                  max_initials=1,
                                                  keep_dash=True)
        alternatives.append(first_choice)
        logger.debug("Alternatives for %s: %s", account_name, alternatives)
        return alternatives

    def is_cnaddr_free(self, local_part, domain_part):
        addr = "@".join((local_part, domain_part))
        if addr in self.in_use:
            # TODO: Why is this not populated?
            logger.warning('address %s already in use', addr)
            return False
        elif addr in self.new_addrs:
            logger.warning('address %s reserved in transaction', addr)
            return False
        return True

    def reserve_addr(self, account_name, domain_part):
        attempts = set()
        for local_part in self.get_alternatives(account_name):
            addr = format_addr(local_part, domain_part)
            if self.is_cnaddr_free(local_part, domain_part):
                self.new_addrs.add(addr)
                return (local_part, domain_part)
            else:
                attempts.add(addr)

        raise ValueError("No free addresses found (%r)" % (attempts))


def get_sito_persons(db):
    co = Factory.get('Constants')(db)
    pe = Factory.get('Person')(db)
    for row in pe.list_affiliations(source_system=co.system_sito):
        yield int(row['person_id'])


def process_mail(db):
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    # TODO: Use `Email` module logger
    em = Email.email_address(db, logger=logger.getChild('email_address'))

    generate_addr = AddressGenerator(db)
    spread = co.spread_uit_exchange

    logger.info("Fetching all sito persons...")
    sito_persons = list(get_sito_persons(db))
    logger.info("Got %s persons", len(sito_persons))

    exch_users = dict()
    uname2accid = dict()
    ownerid2uname = dict()
    stats = {'included': 0, 'skipped': 0}

    logger.info("Fetching all sito accounts with %r spread...", spread)
    for a in ac.search(spread=spread):
        if not a['name'].endswith(sito_postfix):
            stats['skipped'] += 1
            continue
        if a['owner_id'] not in sito_persons:
            stats['skipped'] += 1
            continue

        stats['included'] += 1
        exch_users[a['account_id']] = a['name']
        uname2accid[a['name']] = a['account_id']
        ownerid2uname.setdefault(a['owner_id'], []).append(a['name'])
    logger.info('Got %d accounts (%d considered, %d skipped)',
                stats['included'], sum(stats.values()), stats['skipped'])
    logger.debug("%d account ids, %d usernames",
                 len(exch_users), len(uname2accid))

    for owner, usernames in (t for t in ownerid2uname.items()
                             if len(t[1]) > 1):
        logger.debug("owner_id=%r has %d accounts: %s",
                     owner, len(usernames), usernames)

    logger.info("Fetching all sito email targets...")
    sito_mails = dict()
    for uname, data in ac.getdict_uname2mailinfo().items():
        if uname not in uname2accid:
            continue
        # this is a sito user
        for row in filter(lambda r: r['domain'] == sito_domain, data):
            sito_mails[uname] = format_addr(row['local_part'], row['domain'])
    logger.info('Got email address for %d sito accounts', len(sito_mails))

    # list to hold those we will build addresses for
    all_emails = dict()

    for account_id, uname in exch_users.items():
        if uname in sito_mails:
            logger.debug("User %s has existing address %r",
                         uname, sito_mails[uname])
        else:
            logger.info("User %s does not have an address!", uname)
            try:
                cn_addr = generate_addr.reserve_addr(uname, sito_domain)
                all_emails.setdefault(account_id, []).append(cn_addr)
            except Exception:
                logger.error('Unable to generate email address for %r/%r',
                             uname, sito_domain, exc_info=True)

    # update all email addresses
    logger.debug('Updating %d sito addresses', len(all_emails))
    for acc_id, emaillist in all_emails.items():
        for local_part, domain_part in emaillist:
            # TBD: is_primary always set to True?
            is_primary = True
            addr = format_addr(local_part, domain_part)
            logger.info('Setting address for %r to %r (primary=%r)',
                        acc_id, addr, is_primary)
            em.process_mail(acc_id, addr, is_primary=is_primary)


default_log_preset = getattr(cereconf, 'DEFAULT_LOGGER_TARGET', 'console')


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Process accounts for SITO employees")

    add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf(default_log_preset, args)

    logger.info('Start of %s', parser.prog)
    logger.debug('args: %r', args)

    db = Factory.get('Database')()
    db.cl_init(change_program=parser.prog)

    process_mail(db)

    if args.commit:
        logger.info('Commiting changes')
        db.commit()
    else:
        db.rollback()
        logger.info('Rolling back changes')
    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
