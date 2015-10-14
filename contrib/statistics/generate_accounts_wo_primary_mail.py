#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2015 University of Oslo, Norway
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

import sys
import cerebrum_path
from Cerebrum.Utils import Factory
from Cerebrum import Errors
"""
Generate an HTML formatted report of accounts belonging to a person with
the specified spread, that are missing primary email addresses.
"""

def get_accounts_wo_primary_email(logger, expired, spread_name):
    """
    Returns a list of all accounts owned by an entity_person with the
    specified spread, but don't have a primary mail-address.

    @param logger:  Logger to use.
    @type  logger:  CerebrumLogger

    @param expired: If True, include expired accounts. Defaults to False.
    @type  expired: bool

    @param spread_name: Name of spread to filter user search by.
    @type  spread_name: String

    @return List of account names that is missing a primary email address.
    """

    # Database-setup
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    #
    try:
        spread = getattr(co, spread_name)
    except AttributeError:
        logger.error('Spread not found, exiting..')
        sys.exit(2)

    # Return-list
    users_wo_pri = []    # List to contain results

    # Fetch account list
    if expired:
        users = ac.search(spread=spread,
                          owner_type=co.entity_person,
                          expire_start=None)
    else:
        users = ac.search(spread=spread,
                          owner_type=co.entity_person)

    for user in users:
        # Select the account
        ac.clear()
        try:
            ac.find(user['account_id'])
        except Errors.NotFoundError:
            logger.error('Can\'t find account with id %d' % user['account_id'])
            continue

        try:
            ac.get_primary_mailaddress()
        except Errors.NotFoundError:
            users_wo_pri.append(ac.account_name)

    return users_wo_pri


def gen_html_report(output, title, account_names):
    output.write("""<html>
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">
        <title>%s</title>
    </head>
    <body>
    """ % title)

    output.write('<h2>%d accounts</h2>\n' % len(account_names))
    output.write('<h3>Usernames</h3>\n')
    output.write('<ul>\n')

    for name in account_names:
        output.write('<li>%s</li>\n' % name)

    output.write('</ul>\n</body>\n</html>\n')

def main():
    try:
        import argparse
    except ImportError:
        import Cerebrum.extlib.argparse as argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-s', '--spread',
                        dest='spread',
                        help='Name of spread to filter accounts by.',
                        required=True)
    parser.add_argument('-o', '--output',
                        dest='output_file',
                        help='Output file for report. Default is stdout.')
    parser.add_argument('-i', '--include-expired',
                        action='store_true',
                        help='Include expired accounts.')
    parser.add_argument('-l', '--logger-name',
                        dest='logname',
                        default='cronjob',
                        help='Specify logger (default: cronjob).')
    args = parser.parse_args()

    logger = Factory.get_logger(args.logname)

    if args.output_file is not None:
        try:
            output = open(args.output_file, 'w')
        except IOError, e:
            logger.error(e)
            sys.exit(1)
    else:
        output = sys.stdout

    logger.info('Reporting accounts w/o primary email and spread: %s' %
                args.spread)
    accounts = get_accounts_wo_primary_email(logger,
                                             args.include_expired,
                                             args.spread)
    title = 'Accounts without primary email and spread: %s' % args.spread
    gen_html_report(output, title, accounts)
    logger.info('Done reporting accounts w/o primary email and spread: %s' %
                args.spread)

    if args.output_file is not None:
        output.close()

if __name__ == '__main__':
    main()
