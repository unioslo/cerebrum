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
""" Generate an HTML report with accounts missing primary email address.

Accounts should have a primary email address if they are owned by a person, and
lacks an email spread.
"""
import argparse
import datetime
import logging
import sys

from jinja2 import Environment
from six import text_type

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.modules.Email import EmailTarget
from Cerebrum.utils.argutils import codec_type, get_constant

logger = logging.getLogger(__name__)
now = datetime.datetime.now


# TODO: Move to actual template, or at least use a base template
template = u"""
<!DOCTYPE html>
<html>
  <head>
    <meta http-equiv="Content-Type"
          content="text/html; charset={{ encoding | default('utf-8') }}">
    <title>{{ title | default('Accounts without primary address') }}</title>
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
        width: 100%%;
        text-align: left;
      }
      table thead {
        border-bottom: solid gray 1px;
      }
      table th, table td {
        padding: .5em 1em;
        width: 10%%;
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
      {{ usernames | length }} account(s) without primary email address
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


def get_entities_with_primary_addr(db):
    """ Get the target entity_id of primary email addresses. """
    et = EmailTarget(db)
    for r in et.list_email_target_primary_addresses():
        if r['target_entity_id'] is None:
            # Some targets don't have a target entity (sympa, rt, pipes, ...)
            continue
        yield int(r['target_entity_id'])


def get_accounts_wo_primary_addr(db, spread, include_expired):
    """ Generate usernames of accounts that are missing primary email address.

    Returns a list of all accounts owned by an entity_person with the
    specified spread, but don't have a primary mail-address.

    :param db:
        A cerebrum database connection

    :param spread:
        The SpreadCode to search by.

    :param bool include_expired:
        Include expired accounts iff set to True.

    :return generator:
        A generator that yields account names.
    """
    # Database-setup
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)

    logger.debug('caching entities with primary address...')
    entities = set(get_entities_with_primary_addr(db))
    logger.debug('... found %d entity targets with primary address',
                 len(entities))

    logger.debug('finding accounts...')
    search_args = {
        'owner_type': co.entity_person,
        'spread': spread,
    }
    if include_expired:
        search_args['expire_start'] = None

    for user in ac.search(**search_args):
        if int(user['account_id']) in entities:
            continue

        username = user['name'].decode(db.encoding)

        logger.info('No primary address for %s', username)
        yield username


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
        '-i', '--include-expired',
        action='store_true',
        default=False,
        help='include expired accounts')

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)

    spread = get_constant(db, parser, co.Spread, args.spread, spread_arg)

    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %r", args)
    logger.info("spread: %s", text_type(spread))

    accounts = list(get_accounts_wo_primary_addr(db,
                                                 spread,
                                                 args.include_expired))

    title = ('Accounts without primary email and spread=%s' %
             text_type(spread))
    write_html_report(args.output, args.codec, title, accounts)

    args.output.flush()
    if args.output is not sys.stdout:
        args.output.close()

    logger.info('Report written to %s', args.output.name)
    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
