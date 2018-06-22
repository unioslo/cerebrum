#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2017-2018 University of Oslo, Norway
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
""" Generate an HTML report with all np_type accounts owned by groups. """

import argparse
import datetime
import logging
import os
import sys
from collections import defaultdict

import jinja2
from six import text_type

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import codec_type

logger = logging.getLogger(__name__)
now = datetime.datetime.now


def accounts_with_group_owner(db):
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    gr = Factory.get('Group')(db)
    accounts = list()
    for account in ac.search(owner_type=co.entity_group):
        keys = ('account_id', 'account_name', 'owner_id', 'owner_type',
                'expire_date')
        entry = dict(zip(keys, account))
        accounts.append(entry)
    group_ids = set(x['owner_id'] for x in accounts)
    group_names = dict(map(lambda x: (x['group_id'], x['name']),
                           gr.search(group_id=group_ids,
                                     filter_expired=False)))
    for account in accounts:
        account['owner_name'] = group_names.get(account['owner_id'])
    return accounts


def add_quarantines_for_accounts(db, accounts):
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    account_ids = set(x['account_id'] for x in accounts)
    rows = ac.list_entity_quarantines(
        entity_ids=account_ids,
        only_active=True)
    quarantines = defaultdict(list)
    for row in rows:
        quarantines[row['entity_id']].append(
            text_type(co.Quarantine(row['quarantine_type'])))
    for account in accounts:
        account['quarantines'] = ', '.join(
            quarantines[account['account_id']])
    return accounts


def add_group_memberships(db, accounts, show_membership_in):
    gr = Factory.get('Group')(db)
    account_ids = set(x['account_id'] for x in accounts)
    memberships = defaultdict(list)
    for group_name in show_membership_in:
        gr.clear()
        gr.find_by_name(group_name)
        for row in gr.search_members(group_id=gr.entity_id):
            if row['member_id'] in account_ids:
                memberships[row['member_id']].append(group_name)
    for account in accounts:
        account['group_memberships'] = ', '.join(
            memberships[account['account_id']])
    return accounts


def write_html_report(stream, codec, accounts, summary):
    output = codec.streamwriter(stream)

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(
            os.path.join(os.path.dirname(__file__),
                         'templates')))
    template = env.get_template('simple_list_overview.html')
    output.write(
        template.render(
            headers=(
                ('account_name', u'Account name'),
                # ('account_id', u'Account ID'),
                ('owner_name', u'Owner group name'),
                # ('owner_id', u'Owner group ID'),
                # ('expire_date', u'Account expire_date'),
                ('quarantines', u'Active quarantines'),
                ('group_memberships', u'Member of'),
                ),
            title=u'Accounts owned by a group ({timestamp})'.format(
                timestamp=now().strftime('%Y-%m-%d %H:%M:%S')),
            encoding=codec.name,
            prelist=u'<h3>Accounts owned by a group</h3>' +
                    u''.join([u'<p>{}</p>'.format(x) for x in summary]),
            items=accounts,
        )
    )
    output.write("\n")


DEFAULT_ENCODING = 'utf-8'


def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-o', '--output',
        metavar='FILE',
        type=argparse.FileType('w'),
        default='-',
        help='Output file for report, defaults to stdout')
    parser.add_argument(
        '-e', '--encoding',
        dest='codec',
        default=DEFAULT_ENCODING,
        type=codec_type,
        help="Output file encoding, defaults to %(default)s")
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

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %r", args)

    db = Factory.get('Database')()

    def _u(db_value):
        if isinstance(db_value, bytes):
            return db_value.decode(db.encoding)
        return db_value

    summary = []
    accounts = accounts_with_group_owner(db)
    accounts = add_quarantines_for_accounts(db, accounts)

    accounts = [dict((k, _u(v)) for k, v in account_info.items())
                for account_info in accounts]

    if args.ignore_groups:
        accounts = [a for a in accounts
                    if a['owner_name'] not in args.ignore_groups]
        summary.append(u'Ignoring accounts owned by: {}'.format(
            ', '.join(args.ignore_groups)))

    if args.show_membership_in:
        accounts = add_group_memberships(db, accounts, args.show_membership_in)
        summary.append(u'Checking for membership in: {}'.format(
            ', '.join(args.show_membership_in)))

    sorted_accounts = sorted(accounts,
                             key=lambda x: (x['owner_name'],
                                            x['account_name']))

    summary.append(u'Found {0} accounts'.format(len(accounts)))
    logger.info(summary)

    write_html_report(args.output, args.codec, sorted_accounts, summary)

    args.output.flush()
    if args.output is not sys.stdout:
        args.output.close()

    logger.info('Report written to %s', args.output.name)
    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
