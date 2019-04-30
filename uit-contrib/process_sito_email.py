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
from __future__ import absolute_import, print_function

import getopt
import sys

import mx.DateTime

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.funcwrap import memoize
from Cerebrum.modules.no.uit import Email
from Cerebrum.modules.Email import EmailDomain, EmailAddress


progname = __file__.split("/")[-1]
__doc__ = """
This script creates/updates email addresses for all accounts in
cerebrum that has a email spread

usage:: %s [options]

options are
    -h | --help     : show this
    -d | --dryrun   : do not change DB
    --logger-name name   : log name to use
    --logger-level level : log level to use
""" % (progname, )

# initialise Cerebrum objects
db = Factory.get('Database')()
ac = Factory.get('Account')(db)
p = Factory.get('Person')(db)
co = Factory.get('Constants')(db)
db.cl_init(change_program=progname)
logger = Factory.get_logger('cronjob')
em = Email.email_address(db, logger=logger)

# script variables
try_only_first = True
sito_addresses_in_use = list()
sito_addresses_new = list()


def _get_alternatives(account_name):
    ac.clear()
    ac.find_by_name(account_name)
    alternatives = list()
    first_choise = ac.get_email_cn_local_part(given_names=1,
                                              max_initials=1,
                                              keep_dash=True)
    alternatives.append(first_choise)
    logger.debug("Alternatives for %s: %s", account_name, alternatives)
    return alternatives


@memoize
def get_domainid(domain_part):
    domain = EmailDomain(db)
    domain.find_by_domain(domain_part)
    return domain.entity_id


def is_cnaddr_free(local_part, domain_part):

    addr = "@".join((local_part, domain_part))
    if addr in sito_addresses_in_use:
        logger.error("Address %s not free, in DB", addr)
        return False
    elif addr in sito_addresses_new:
        logger.error("Addres %s not free, in new set", addr)
        return False
    return True


def is_cnaddr_free_old(local_part, domain_part):
    domain_id = get_domainid(domain_part)
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


def get_cn_addr(username, domain):
    dom_part = domain
    alternatives = _get_alternatives(username)
    if try_only_first:
        logger.info("Trying only first alternative")
        alternatives = alternatives[:1]
        for em_addr in alternatives:
            if is_cnaddr_free(em_addr, dom_part):
                return (em_addr, dom_part)
    else:
        logger.error("NOT IMPLEMENTED. Using more than first suggested "
                     "emailaddr")
    return None, dom_part


def process_mail():
    logger.info("Get all SiTo persons")
    sito_persons = list()
    for row in p.list_affiliations(source_system=co.system_sito):
        sito_persons.append(row['person_id'])
    logger.info("Got %s sito persons", len(sito_persons))

    logger.info("Get all accounts with exchange@uit spread from sito")
    exch_users = dict()
    uname2accid = dict()
    ownerid2uname = dict()
    count = 0
    skipped = 0

    # TBD: Use account affiliation = sito to get accounts instead of spread!
    for a in ac.search(spread=co.spread_uit_exchange):
        if (a['name'].endswith(cereconf.USERNAME_POSTFIX.get('sito'))):
            logger.debug("caching sito account %s", a['name'])
        else:
            skipped += 1
            continue

        if a['owner_id'] in sito_persons:
            count += 1
            exch_users[a['account_id']] = a['name']
            uname2accid[a['name']] = a['account_id']
            ownerid2uname.setdefault(a['owner_id'], list()).append(a['name'])
        # all_emails.setdefault(account_id,list()).append(uid_addr)
    keys = exch_users.keys()
    keys.sort()
    logger.info("got %d accounts (%s)", len(exch_users), count)
    logger.info("got %d account", len(uname2accid))
    logger.info("skipped %d account", skipped)

    for owner, uname in ownerid2uname.items():
        if len(uname) > 1:
            logger.debug("Owner %s has %s accounts: %s", owner, len(uname),
                         uname)

    sito_domainname = cereconf.SITO_PRIMARY_MAILDOMAIN
    logger.info("get all email targets for sito")
    sito_mails = dict()
    for uname, data in ac.getdict_uname2mailinfo().items():
        # only sito
        if uname2accid.get(uname, None):
            # this is a sito user
            for me in data:
                if me['domain'] == sito_domainname:
                    sito_mails[uname] = "@".join((me['local_part'],
                                                  me['domain']))

    # list to hold those we will build addresses for
    all_emails = dict()

    for account_id, uname in exch_users.items():
        old_addr = sito_mails.get(uname, None)
        if old_addr:
            logger.debug("Got %s as existing mailaddress for %s", old_addr,
                         uname)
        else:
            logger.info("user %s does not hava a sito address!, BUILD", uname)
            cn_addr = get_cn_addr(uname, sito_domainname)
            if cn_addr:
                logger.debug("Will use %s for %s", cn_addr, uname)
                all_emails.setdefault(account_id, list()).append(cn_addr)
                sito_addresses_new.append(cn_addr)
            else:
                logger.error("Got NOADRESS for %s, check logs", uname)

    # update all email addresses
    logger.debug("Ready to update %s sito addresses", len(all_emails))
    for acc_id, emaillist in all_emails.items():
        for addr in emaillist:
            # TBD: is_primary always set to True?
            is_primary = True
            addr = "@".join((addr[0], addr[1]))
            logger.info("Set mailaddr: %s/%s, primary=%s", acc_id, addr,
                        is_primary)
            em.process_mail(acc_id, addr, is_primary=is_primary)


def main():
    global persons, accounts
    starttime = mx.DateTime.now()

    try:
        opts, args = getopt.getopt(
            sys.argv[1:],
            'dh',
            ['dryrun', 'help'])
    except getopt.GetoptError as m:
        usage(1, m)

    dryrun = False
    for opt, val in opts:
        if opt in ('-d', '--dryrun'):
            dryrun = True
        elif opt in ('-h', '--help'):
            usage()

    process_mail()

    if dryrun:
        db.rollback()
        logger.info("Dryrun, rollback changes")
    else:
        db.commit()
        logger.info("Committing all changes to DB")

    endtime = mx.DateTime.now()
    logger.debug("Started %s ended %s", starttime, endtime)
    logger.debug("Script running time was %s",
                 (endtime - starttime).strftime("%M minutes %S secs"))


def usage(exitcode=0, msg=None):
    if msg:
        print(msg)
    print(__doc__)
    sys.exit(exitcode)


if __name__ == '__main__':
    main()
