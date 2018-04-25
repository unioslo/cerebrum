#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
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
""" Generate an HTML report with accounts that are missing mail spread.

Accounts are missing mail spread if they are owned by a person, which lacks the
specified mail spread, but still has an email_target of type 'account'.
"""
import argparse
import codecs
import datetime
import logging
import sys
from collections import defaultdict, Mapping

from jinja2 import Environment
from six import text_type

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Entity import EntitySpread
from Cerebrum.Utils import Factory
from Cerebrum.modules.Email import EmailTarget


logger = logging.getLogger(__name__)
now = datetime.datetime.now


# TODO: Move to actual template, or at least use a base template
template = u"""
<!DOCTYPE html>
<html>
  <head>
    <meta http-equiv="Content-Type"
          content="text/html; charset={{ encoding | default('utf-8') }}">
    <title>{{ title | default('Users missing mail spread') }}</title>
    <style type="text/css">
      /* <![CDATA[ */
      h1 {
        margin: 1em .8em 1em .8em;
        font-size: 1.4em;
      }
      h2 {
        margin: 1.5em 1em 1em 1em;
        font-size: 1em;
      }
      table + h1 {
        margin-top: 3em;
      }
      table {
        border-collapse: collapse;
        width: 100%;
        text-align: left;
      }
      table thead {
        border-bottom: solid gray 1px;
      }
      table th, table td {
        padding: .5em 1em;
        width: 10%;
      }
      .meta {
        color: gray;
        text-align: right;
      }
      /* ]] >*/
    </style>
  </head>
  <body>
    <p class="meta">
      {{ usernames | length }} account(s) with missing mail spread
    </p>

    <h2>Usernames</h2>
    <ul>
      {% for username in usernames %}
      <li>{{ username }}</li>
      {% endfor %}
    </ul>

    <p class="meta">
      Generated: {{ when }}
    </p>
  </body>
</html>
""".strip()


class ExcludeLookup(object):
    """ Check for membership in a list if groups. """

    def __init__(self, db, names):
        self.db = db
        self.groups = dict()
        for group_name in names:
            gr = Factory.get('Group')(db)
            gr.find_by_name(group_name)
            self.groups[gr.group_name] = gr

    def __contains__(self, member_id):
        return any(gr.has_member(member_id)
                   for gr in self.groups.values())


class SpreadLookup(Mapping):
    """ Cache spreads for given entity types. """

    def __init__(self, db, entity_types):
        es = EntitySpread(db)
        data = defaultdict(set)
        for e_id, s_code in es.list_all_with_spread(entity_types=entity_types):
            data[e_id].add(s_code)
        self.data = dict(data)

    def __getitem__(self, item):
        return self.data[item]

    def __iter__(self):
        return iter(self.data)

    def __len__(self):
        return len(self.data)


def get_accounts(db, spread, include_expired=False, exclude_groups=None):
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
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    et = EmailTarget(db)

    search_args = {'owner_type': co.entity_person}
    if include_expired:
        search_args['expire_start'] = None

    logger.debug('looking up excluded groups...')
    excluded = ExcludeLookup(db, exclude_groups)

    logger.debug('caching accounts spreads...')
    account_spreads = SpreadLookup(db, co.entity_account)

    # for account in accounts:
    for account in ac.search(**search_args):

        if account['account_id'] not in account_spreads:
            # is_deleted() or is_reserved()
            continue

        if int(spread) in account_spreads[account['account_id']]:
            continue

        if account['account_id'] in excluded:
            logger.debug('Ignoring %s (%d), member of excluded group',
                         account['name'])
            continue

        # Find EmailTarget for account
        et.clear()
        try:
            et.find_by_target_entity(account['account_id'])
        except Errors.NotFoundError:
            logger.info('No email targets for account with id %d',
                        account['account_id'])
            continue

        if et.email_target_type == co.email_target_account:
            yield account['name']


def write_html_report(stream, codec, title, usernames):
    output = codec.streamwriter(stream)
    template_env = Environment(trim_blocks=True, lstrip_blocks=True)
    report = template_env.from_string(template)

    output.write(
        report.render({
            'title': title,
            'encoding': codec.name,
            'usernames': usernames,
            'when': now().strftime('%Y-%m-%d %H:%M:%S'),
        })
    )
    output.write('\n')


def codec_type(encoding):
    try:
        return codecs.lookup(encoding)
    except LookupError as e:
        raise ValueError(str(e))


DEFAULT_ENCODING = 'utf-8'


def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-o', '--output',
        metavar='FILE',
        type=argparse.FileType('w'),
        default='-',
        help='output file for report, defaults to stdout')
    parser.add_argument(
        '-e', '--encoding',
        dest='codec',
        default=DEFAULT_ENCODING,
        type=codec_type,
        help="output file encoding, defaults to %(default)s")
    spread_arg = parser.add_argument(
        '-s', '--spread',
        dest='spread',
        required=True,
        help='name of spread to filter accounts by')
    parser.add_argument(
        '-g', '--exclude_groups',
        dest='excluded_groups',
        help='comma-separated list of groups to be excluded from the report')
    parser.add_argument(
        '-i', '--include-expired',
        action='store_true',
        default=False,
        help='include expired accounts')

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)

    spread = co.human2constant(args.spread, co.Spread)
    if not spread:
        raise argparse.ArgumentError(
            spread_arg, 'invalid spread {}'.format(repr(args.spread)))

    excluded_groups = []
    if args.excluded_groups is not None:
        excluded_groups.extend(args.excluded_groups.split(','))

    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %r", args)

    accounts = list(get_accounts(db,
                                 spread,
                                 args.include_expired,
                                 excluded_groups))

    title = ('Accounts with email_target=account, without spread=%s' %
             text_type(spread))
    write_html_report(args.output, args.codec, title, accounts)

    args.output.flush()
    if args.output is not sys.stdout:
        args.output.close()

    logger.info('Report written to %s', args.output.name)
    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
