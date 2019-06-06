#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2012-2018 University of Oslo, Norway
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
""" Generate an HTML or CSV report with non-affiliated accounts.

This program reports users on disk without affiliations, and any quarantines
that are ACTIVE for that user.
"""
import argparse
import csv
import datetime
import logging
import sys

from jinja2 import Environment
from six import text_type

import Cerebrum.logutils
import Cerebrum.logutils.options
import Cerebrum.utils.csvutils as _csvutils
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import codec_type, get_constant

logger = logging.getLogger(__name__)
now = datetime.datetime.now

# TODO: Move to actual template, or at least use a base template
template = u"""
{# HTML template for 'generate_accounts_without_affiliations.py'
 # Note: this template requires a custom filter, sort_by_quarantine
-#}
<!DOCTYPE html>
<html>
  <head>
    <meta http-equiv="Content-Type"
          content="text/html; charset={{ encoding | default('utf-8') }}">
    <title>{{ title | default('Users on disk without affiliations') }}</title>
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
      {{ num_accounts }} account(s) on disk {{ criteria }}
    </p>

    {% for disk in disks | sort %}
    <h2>{{ disk }}</h2>
    <table>
      <thead>
        <tr>
          <th>Username</th>
          <th>Full Name</th>
          <th>Quarantine type</th>
          <th>Quarantine description</th>
          <th>Quarantine start date</th>
        </tr>
      </thead>

      {% for user in disks[disk] | sort_by_quarantine %}
      <tr>
        <td>{{ user['account_name'] }}</td>
        <td>{{ user['full_name'] }}</td>
        <td>{{ user['quarantine']['type'] }}</td>
        <td>{{ user['quarantine']['description'] }}</td>
        <td>{{ user['quarantine']['date_set'] }}</td>
      </tr>
      {% endfor %}
    </table>

    {% endfor %}

    <p class="meta">
      Generated: {{ when }}
    </p>
  </body>
</html>
""".strip()


class CsvDialect(csv.excel):
    """Specifying the CSV output dialect the script uses.

    See the module `csv` for a description of the settings.

    """
    delimiter = ';'
    lineterminator = '\n'


def get_accs_wo_affs(db, target_spread, check_accounts=False):
    """ Search disks for users owned by persons without affiliations.

    :return dict:
        A mapping from *disk name* to a list of unaffiliated users.  Each user
        is a dict with the following user info:

        - account_name: account name
        - full_name:    full name
        - quarantine:
            - type:         the type of the quarantine
            - description:  general description
            - date_set:     The date the quarantine was set

    """
    logger.info("Fetching accounts...")

    ac = Factory.get('Account')(db)
    pe = Factory.get('Person')(db)
    di = Factory.get('Disk')(db)
    co = Factory.get('Constants')(db)

    def _u(db_value):
        if isinstance(db_value, bytes):
            return db_value.decode(db.encoding)
        return db_value

    def _row_to_quar(row):
        """ list_entity_quarantines row to dict """
        return {
            'type': text_type(co.Quarantine(row['quarantine_type'])),
            'description': _u(row['description']),
            'date_set': text_type(row['start_date'].strftime('%Y-%m-%d')),
        }

    no_aff = {}

    # Cache the person affiliations
    target_person_affs = set((
        row['person_id'] for row in pe.list_affiliations()))

    # Counter values, number of disks checked and number of accounts checked.
    stats = {'disk': 0, 'user': 0}

    # We iterate over the disks:
    for d in di.list():
        # We only want disks with target spread
        if d['spread'] != target_spread:
            continue

        logger.debug("Targeting disk: %s", _u(d['path']))
        stats['disk'] += 1

        # We only pull users from NIS_user@uio..
        users = ac.list_account_home(disk_id=d['disk_id'],
                                     home_spread=target_spread)
        logger.debug("Users found on disk: %d", len(users))

        for u in users:
            ac.clear()
            try:
                ac.find(u['account_id'])
            except Errors.NotFoundError:
                logger.warn("Can't find account_id=%r", u['account_id'])
                continue
            stats['user'] += 1
            # Exclude non personal accounts:
            if ac.owner_type != co.entity_person:
                continue
            # If we're focusing on person affiliations,
            # ignore persons with an affiliation:
            if not check_accounts and ac.owner_id in target_person_affs:
                continue
            # If we're focusing on account affiliations,
            # ignore persons without an affiliation and
            # accounts with an affiliation
            if check_accounts and (ac.get_account_types() != [] or
                                   ac.owner_id not in target_person_affs):
                continue

            quar = ac.get_entity_quarantine(only_active=True)
            report_item = {
                'account_name': _u(ac.account_name),
                'full_name': _u(ac.get_fullname()),
                'quarantine': _row_to_quar(quar[0]) if len(quar) else {},
            }
            no_aff.setdefault(_u(d['path']), []).append(report_item)

    logger.debug('%(disk)d disks and %(user)d accounts checked', stats)
    logger.info('... fetched %d users on disk without affiliations',
                sum(len(users) for users in no_aff.values()))
    return no_aff


def do_sort_by_quarantine(l):
    """ Sort by 'has quarantine'. """
    return sorted(l, cmp=lambda a, b: cmp(len(a['quarantine']),
                                          len(b['quarantine'])))


def write_csv_report(stream, codec, no_aff, check_accounts):
    """ Write a CSV report to an open bytestream. """
    number_of_users = sum(len(users) for users in no_aff.values())

    output = codec.streamwriter(stream)
    output.write('# Encoding: %s\n' % codec.name)
    output.write('# Generated: %s\n' % now().strftime('%Y-%m-%d %H:%M:%S'))
    output.write('# Number of users found: %d\n' % number_of_users)

    writer = _csvutils.UnicodeWriter(output, dialect=CsvDialect)

    for disk_path in sorted(no_aff):
        for user in do_sort_by_quarantine(no_aff[disk_path]):
            quarantine = user['quarantine'] or ''
            if quarantine:
                quarantine = ','.join(quarantine.get(a) or ''
                                      for a in ('type', 'description',
                                                'date_set'))
            writer.writerow((
                disk_path,
                user['account_name'],
                user['full_name'],
                quarantine,
            ))
    return


def write_html_report(stream, codec, no_aff, check_accounts):
    """ Write an HTML report to an open bytestream. """
    output = codec.streamwriter(stream)
    template_env = Environment(trim_blocks=True, lstrip_blocks=True)
    template_env.filters['sort_by_quarantine'] = do_sort_by_quarantine

    number_of_users = sum(len(users) for users in no_aff.values())
    if check_accounts:
        criteria = ('without affiliations, owned by persons with'
                    ' affiliations')
    else:
        criteria = 'without person affiliations'
    report = template_env.from_string(template)
    output.write(
        report.render({
            'disks': no_aff,
            'num_accounts': number_of_users,
            'criteria': criteria,
            'when': now().strftime('%Y-%m-%d %H:%M:%S'),
            'encoding': codec.name,
        })
    )
    output.write('\n')


FORMATS = {
    'csv': write_csv_report,
    'html': write_html_report,
}

DEFAULT_FORMAT = 'html'
DEFAULT_SPREAD = 'NIS_user@uio'
DEFAULT_ENCODING = 'utf-8'


def main(inargs=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-o', '--output',
        metavar='FILE',
        type=argparse.FileType('w'),
        default='-',
        help='The file to print the report to, defaults to stdout')
    parser.add_argument(
        '-f', '--output-format',
        choices=FORMATS.keys(),
        default=DEFAULT_FORMAT,
        help='Output file format, defaults to %(default)s')
    parser.add_argument(
        '-e', '--encoding',
        dest='codec',
        default=DEFAULT_ENCODING,
        type=codec_type,
        help="Output file encoding, defaults to %(default)s")
    spread_arg = parser.add_argument(
        '-s', '--spread',
        metavar='SPREAD',
        default=DEFAULT_SPREAD,
        help='Spread to filter users by, defaults to %(default)s')
    parser.add_argument(
        '-a', '--check-accounts',
        action='store_true',
        default=False,
        help='Find accounts without affiliations, but where the owner'
             ' has affiliations.  The default is to find accounts of persons'
             ' without affiliations')

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    # Initialization of database connection
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)

    spread = get_constant(db, parser, co.Spread, args.spread, spread_arg)

    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %r", args)
    logger.info("spread: %s", text_type(spread))

    # Search for accounts without affiliations
    no_aff = get_accs_wo_affs(db, spread, args.check_accounts)

    # Generate report of results
    writer = FORMATS[args.output_format]
    writer(args.output, args.codec, no_aff, args.check_accounts)
    args.output.flush()

    # If the output is being written to file, close the filehandle
    if args.output is not sys.stdout:
        args.output.close()

    logger.info('Report written to %s', args.output.name)
    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
