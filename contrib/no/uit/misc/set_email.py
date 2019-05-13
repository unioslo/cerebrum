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
from __future__ import print_function

import getopt
# import os
import re
import sys

import cereconf
# from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uit import Email


progname = __file__.split("/")[-1]
__doc__ = """
This utility creates an exchange email for a user.

usage:: %s [options]

options are
    -a | --account  : account name to modify
    -e | --email    : exhange email address to set
    -n | --noprimary: do not set this to primary
    -h | --help     : show this
    -d | --dryrun   : do not change DB
    --logger-name name   : log name to use
    --logger-level level : log level to use
""" % (progname, )


logger = Factory.get_logger('cronjob')
db = Factory.get('Database')()
ac = Factory.get('Account')(db)
co = Factory.get('Constants')(db)
db.cl_init(change_program=progname)
em = Email.email_address(db, logger=logger)

valid_exchange_domains = [cereconf.NO_MAILBOX_DOMAIN_EMPLOYEES, ]

validate = re.compile(r'^(([\w-]+\.)+[\w-]+|([a-zA-Z]{1}|[\w-]{2,}))$')


def set_mail(account, localpart, domain, is_primary=True):
    # Validate localpart
    if not validate.match(localpart) or localpart[len(localpart)-1:] == '-':
        raise ValueError('Invalid localpart (%r)' % (localpart, ))

    # Set / validate domain
    # NOTE: Cannot use find_by_domain because we have lots of invalid domains
    #       in our domain table!
    if (
            domain != 'adm.uit.no' and
            domain != 'hin.no' and
            domain != 'hih.no' and
            domain != 'nordnorsk.vitensenter.no' and
            domain != 'kun.uit.no' and
            domain != 'post.uit.no' and
            domain not in valid_exchange_domains and
            domain != 'student.uit.no' and
            domain != 'nuv.no' and
            domain != 'norgesuniversitetet.no' and
            domain != 'sito.no' and
            domain != 'mailbox.uit.no' and
            domain != 'hifm.no' and
            domain != 'asp.uit.no' and
            domain != 'ad.uit.no' and
            domain != 'ak.uit.no' and
            domain != 'jusshjelpa.uit.no' and
            domain != 'driv.no' and
            domain != 'samskipnaden.no'):
        logger.error('Can only set emails for domains: %r',
                     valid_exchange_domains)
        raise ValueError('Invalid domain (%r)' % (domain, ))

    # Find account
    ac.clear()
    try:
        ac.find_by_name(account)
    except Exception:
        logger.error('Account name=%r not found', (account))
        sys.exit(0)

    # Re-build email address
    email = '%s@%s' % (localpart, domain)

    # Set email address in ad email table
    if is_primary:
        ac.set_ad_email(localpart, domain)

    # Update email tables immediately
    logger.info('Running email processing for account name=%r', account)
    em.process_mail(ac.entity_id, email, is_primary)


def main():

    try:
        opts, args = getopt.getopt(
            sys.argv[1:],
            'a:e:ndh',
            ['account=', 'email=', 'noprimary', 'dryrun', 'help'])
    except getopt.GetoptError as m:
        usage(1, m)

    dryrun = False
    account = None
    email = None
    primary = True
    for opt, val in opts:
        if opt in('-d', '--dryrun'):
            dryrun = True
        elif opt in ('-e', '--email='):
            print("email set to:%s" % val)
            email = val
        elif opt in ('-n', '--noprimary'):
            primary = False
        elif opt in ('-a', '--account='):
            print("account set to:%s" % val)
            account = val
        elif opt in ('-h', '--help'):
            usage()

    if account is None or email is None:
        print("you must set account and email \n")
        usage()

    splitmail = email.split('@')
    if len(splitmail) != 2:
        logger.error('You must specify one localpart and one domain. '
                     'E.g. example@test.com')
        usage()
    set_mail(account, splitmail[0], splitmail[1], primary)

    if (dryrun):
        db.rollback()
        logger.info("Dryrun, rollback changes")
    else:
        db.commit()
        logger.info("Committing all changes to DB")


def usage(exitcode=0, msg=None):
    if msg:
        print(msg)
    print(__doc__)
    sys.exit(exitcode)


if __name__ == '__main__':
    main()
