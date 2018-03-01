#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2015-2018 University of Oslo, Norway
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
import argparse

from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.modules.Email import EmailTarget
"""
Generates an HTML formatted report of accounts owned by a person, which lacks
the specified mail spread, but still has an email_target of type 'account'.
"""

logger = Factory.get_logger('console')


def group_names_to_gids(gr, group_names=None):
    """Fetch a list of group-ids from a list of group names.

    @param gr:           Group database connection
    @type  gr:           Cerebrum.Group.Group

    @param group_names:  List of group name strings to process.
                         Defaults to None.
    @type  group_names:  List of strings.

    @return List containing the group id of the groups that were found.
    """
    group_ids = []
    if not group_names:
        return group_ids
    for gname in group_names:
        gr.clear()
        try:
            gr.find_by_name(gname)
        except Errors.NotFoundError:
            logger.warn('No group named %s', gname)
            continue
        group_ids.append(gr.entity_id)
    return group_ids


def get_accs_with_missing_mail_spread(spread_name, expired, exclude):
    """Fetch a list of all accounts with a entity_person owner and IMAP-spread.

    @param spread_name: Name of spread to filter user search by.
    @type  spread_name: String

    @param expired: If True, include expired accounts. Defaults to False.
    @type  expired: bool

    @param exclude: List of group name strings to exclude. Accounts that are
                    members of this group are excluded from the report.
                    Defaults to None.
    @type  exclude: List of strings

    @return List of account names that is missing a primary email address.
    """

    # Database-setup
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    gr = Factory.get('Group')(db)
    et = EmailTarget(db)

    try:
        spread = getattr(co, spread_name)
    except AttributeError:
        logger.error('Spread not found, exiting..')
        sys.exit(2)

    users_wo_mail_spread = []   # List to contain results

    group_ids = group_names_to_gids(gr, exclude)

    # Fetch account list
    if expired:
        accounts = ac.search(owner_type=co.entity_person,
                             expire_start=None)
    else:
        accounts = ac.search(owner_type=co.entity_person)

    for account in accounts:
        ac.clear()
        ac.find(account['account_id'])

        # Ignore if account is deleted or reserved
        if ac.is_deleted() or ac.is_reserved():
            continue

        # Ignore if account has imap spread
        if spread in [row['spread'] for row in ac.get_spread()]:
            continue

        # Check for group membership
        gr.clear()
        is_member = False
        for group_id in group_ids:
            gr.find(group_id)
            if gr.has_member(ac.entity_id):
                is_member = True
                logger.debug('Ignoring %s, member of %s',
                             ac.account_name, gr.group_name)
                break

        if is_member:
            continue

        # Find EmailTarget for account
        et.clear()
        try:
            et.find_by_target_entity(ac.entity_id)
        except Errors.NotFoundError:
            logger.info('No email targets for account with id %d',
                        account['account_id'])
            continue

        if et.email_target_type == co.email_target_account:
            users_wo_mail_spread.append(ac.account_name)

    return users_wo_mail_spread


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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-s', '--spread',
                        dest='spread',
                        help='Name of spread to filter accounts by.',
                        required=True)
    parser.add_argument('-o', '--output',
                        dest='output_file',
                        help='Output file for report. Default is stdout.')
    parser.add_argument('-g', '--exclude_groups',
                        dest='excluded_groups',
                        help='Comma-separated list of groups to be excluded '
                             'from the report.')
    parser.add_argument('-i', '--include-expired',
                        action='store_true',
                        help='Include expired accounts.')
    args = parser.parse_args()

    if args.output_file is not None:
        try:
            output = open(args.output_file, 'w')
        except IOError, e:
            logger.error(e)
            sys.exit(1)
    else:
        output = sys.stdout

    excluded_groups = []
    if args.excluded_groups is not None:
        excluded_groups.extend(args.excluded_groups.split(','))

    logger.info(('Reporting accounts with email_target of type "account", '
                'without spread: %s ' % args.spread))
    accounts = get_accs_with_missing_mail_spread(args.spread,
                                                 args.include_expired,
                                                 excluded_groups)
    title = ('Accounts with email_target of type "account", '
             'without spread: %s' % args.spread)
    gen_html_report(output, title, accounts)
    logger.info(('Done reporting accounts with email_target of type '
                 '"account", without spread: %s ' % args.spread))

    if args.output_file is not None:
        output.close()


if __name__ == '__main__':
    main()
