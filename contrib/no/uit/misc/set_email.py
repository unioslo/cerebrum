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

import argparse
import logging
import re

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uit import Email
from Cerebrum.utils.argutils import add_commit_args

logger = logging.getLogger(__name__)


# NOTE: Cannot use find_by_domain because we have lots of invalid domains
#       in our domain table!
valid_exchange_domains = [
    cereconf.NO_MAILBOX_DOMAIN_EMPLOYEES,
    'ad.uit.no',
    'adm.uit.no',
    'ak.uit.no',
    'asp.uit.no',
    'jusshjelpa.uit.no',
    'kun.uit.no',
    'mailbox.uit.no',
    'post.uit.no',
    'student.uit.no',
    'driv.no',
    'hifm.no',
    'hih.no',
    'hin.no',
    'nordnorsk.vitensenter.no',
    'norgesuniversitetet.no',
    'nuv.no',
    'samskipnaden.no',
    'sito.no',
]

validate = re.compile(r'^(([\w-]+\.)+[\w-]+|([a-zA-Z]{1}|[\w-]{2,}))$')


def set_mail(db, account, localpart, domain, is_primary=True):

    # Validate localpart
    if not validate.match(localpart) or localpart[len(localpart)-1:] == '-':
        raise ValueError('Invalid localpart (%r)' % (localpart, ))

    # Set / validate domain
    if domain not in valid_exchange_domains:
        logger.error('Can only set emails for domains: %r',
                     valid_exchange_domains)
        raise ValueError('Invalid domain (%r)' % (domain, ))

    # Find account
    ac = Factory.get('Account')(db)
    try:
        ac.find_by_name(account)
    except Exception:
        raise ValueError('No account (%r)' % (account, ))

    # Re-build email address
    email = '%s@%s' % (localpart, domain)

    # Set email address in ad email table
    if is_primary:
        ac.set_ad_email(localpart, domain)

    # Update email tables immediately
    logger.info('Running email processing for account name=%r', account)
    em = Email.email_address(db, logger=logger)
    em.process_mail(ac.entity_id, email, is_primary)


def email_type(value):
    lp, _, dom = value.partition('@')
    if not lp:
        raise ValueError('Missing local part')
    if not dom:
        raise ValueError('Missing domain')
    return lp, dom


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="This utility creates an exchange email for a user",
    )
    parser.add_argument(
        '-n', '--noprimary',
        action='store_false',
        dest='primary',
        default=True,
        help='Do not set primary address',
    )

    parser.add_argument(
        'account',
        help='Set email address for account name %(metavar)s',
    )
    parser.add_argument(
        'email',
        type=email_type,
        help='Set email address to %(metavar)s',
    )
    add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('tee', args)

    logger.info('Start of %s', parser.prog)
    logger.debug('args: %r', args)

    db = Factory.get('Database')()
    db.cl_init(change_program=parser.prog)

    try:
        set_mail(db, args.account, args.email[0], args.email[1], args.primary)
    except ValueError as e:
        logger.error('Unable to set email: %s', e)
        raise SystemExit(1)
    except Exception as e:
        logger.error('Unhandled error', exc_info=True)
        raise SystemExit(2)

    if args.commit:
        logger.info('Commiting changes')
        db.commit()
    else:
        logger.info('Rolling back changes')
        db.rollback()
    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
