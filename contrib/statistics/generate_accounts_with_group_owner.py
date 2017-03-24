#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2017 University of Oslo, Norway
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

import argparse
import datetime
import os
import sys
import jinja2

import cereconf

from Cerebrum.Utils import Factory

logger = Factory.get_logger('cronjob')

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)
gr = Factory.get('Group')(db)


def accounts_with_group_owner():
    accounts = list()
    for account in ac.search(owner_type=co.entity_group):
        keys = ('account_id', 'account_name', 'owner_id', 'owner_type',
                'expire_date')
        entry = dict(zip(keys, account))
        accounts.append(entry)
    group_ids = map(lambda x: x['owner_id'], accounts)
    group_names = dict(map(lambda x: (x['group_id'], x['name']),
                           gr.search(group_id=group_ids,
                                     filter_expired=False)))
    for account in accounts:
        account['owner_name'] = group_names.get(account['owner_id'])
    return accounts


def add_quarantines_for_accounts(accounts):
    account_ids = map(lambda x: x['account_id'], accounts)
    rows = ac.list_entity_quarantines(
        entity_ids=account_ids,
        only_active=True)
    quarantines = dict()
    for row in rows:
        quarantines.setdefault(row['entity_id'], []).append(
            str(co.Quarantine(row['quarantine_type'])))
    for account in accounts:
        account['quarantines'] = ', '.join(
            quarantines.get(account['account_id'], []))
    return accounts


def add_group_memberships(accounts, show_membership_in):
    account_ids = map(lambda x: x['account_id'], accounts)
    memberships = {}
    for group_name in show_membership_in:
        gr.clear()
        gr.find_by_name(group_name)
        for row in gr.search_members(group_id=gr.entity_id):
            if row['member_id'] in account_ids:
                memberships.setdefault(row['member_id'], []).append(group_name)
    for account in accounts:
        account['group_memberships'] = ', '.join(memberships.get(
            account['account_id'], []))
    return accounts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-o', '--output',
        type=str,
        dest='output',
        default='',
        help='The file to print the report to. Defaults to stdout.')
    parser.add_argument(
        '-g', '--ignore-group',
        action='append',
        dest='ignore_groups',
        default=[],
        help='Ignore accounts owned by group')
    parser.add_argument(
        '-s', '--show-membership-in',
        action='append',
        dest='show_membership_in',
        default=[],
        help='Check if the accounts are members of this group')
    args = parser.parse_args()

    summary = []
    accounts = accounts_with_group_owner()
    accounts = add_quarantines_for_accounts(accounts)
    if args.ignore_groups:
        accounts = [a for a in accounts
                    if a['owner_name'] not in args.ignore_groups]
        summary.append(u'Ignoring accounts owned by: {}'.format(
            ', '.join(args.ignore_groups)))
    if args.show_membership_in:
        accounts = add_group_memberships(accounts, args.show_membership_in)
        summary.append(u'Checking for membership in: {}'.format(
            ', '.join(args.show_membership_in)))
    sorted_accounts = sorted(accounts,
                             key=lambda x: (x['owner_name'],
                                            x['account_name']))
    iso_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    summary.append(u'{0}: Found {1} accounts'.format(
                   iso_timestamp,
                   len(accounts)))
    logger.info(summary)
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(
            os.path.join(os.path.dirname(__file__),
                         'templates')))
    template = env.get_template('simple_list_overview.html')
    output = template.render(
        headers=(
            ('account_name', u'Account name'),
            #('account_id', u'Account ID'),
            ('owner_name', u'Owner group name'),
            #('owner_id', u'Owner group ID'),
            #('expire_date', u'Account expire_date'),
            ('quarantines', u'Active quarantines'),
            ('group_memberships', u'Member of'),
            ),
        title=u'Accounts owned by a group ({timestamp})'.format(
            timestamp=iso_timestamp),
        prelist=u'<h3>Accounts owned by a group</h3>' +
                u''.join([u'<p>{}</p>'.format(x) for x in summary]),
        items=sorted_accounts).encode('utf-8')
    if args.output:
        with open(args.output, 'w') as fp:
            fp.write(output)
    else:
        sys.stdout.write(output)
    logger.info('{script_name} finished'.format(script_name=sys.argv[0]))

if __name__ == '__main__':
    main()
