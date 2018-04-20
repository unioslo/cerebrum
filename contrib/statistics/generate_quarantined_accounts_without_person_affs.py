#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2018 University of Oslo, Norway
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
""" Generate an HTML report on non-expired, abandoned accounts.

An abandoned account is an account that.
 - has been quarantined for more that a year
 - owned by a person without affiliations

Note that only one quarantine per account is included in the HTML report.
"""
import argparse
import codecs
import logging
import sys
from collections import defaultdict

from jinja2 import Environment
from six import text_type

from mx.DateTime import now, DateTimeDelta

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory


logger = logging.getLogger(__name__)

template = u"""
<!DOCTYPE html>
<html>
  <head>
    <meta http-equiv="Content-Type"
          content="text/html; charset={{ encoding | default('utf-8') }}">
    <title>Quarantined users without person affiliations</title>
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
      {{ num_accounts }} account(s) without person affiliations + not expired +
      quarantined for minimum 1 year
    </p>

    <!-- toc -->
    <table>
      <thead>
        <tr>
          <th>Disk</th>
          <th>Accounts</th>
        </tr>
      </thead>
      <tbody>
        {% for disk in matches | sort %}
        <tr>
          <td><a href="#{{ disk }}">{{ disk }}</a></td>
          <td>{{ matches[disk] | count }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>

    <!-- full output -->
    {% for disk in matches | sort %}
    <a name="{{ disk }}"><h2>{{ disk }}</h2></a>
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
      <tbody>
        {% for user in matches[disk] | sort(attribute='q_date') %}
        <tr>
          <td>{{ user['account_name'] }}</td>
          <td>{{ user['full_name'] }}</td>
          <td>{{ user['q_type'] }}</td>
          <td>{{ user['q_desc'] }}</td>
          <td>{{ user['q_date'] }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>

    {% endfor %}

    <p class="meta">
      Generated: {{ when }}
    </p>
  </body>
</html>
""".strip()


def get_matching_accs(db):
    """ Get defunct account data.

    This function searches the database for accounts where:
      - account is not expired
      - account is owned by a person with no affiliations
      - account has been quarantined for > 1 year

    :return generator:
        A generator that yields dicts with account and quarantine data
    """
    ac = Factory.get('Account')(db)
    pe = Factory.get('Person')(db)
    co = Factory.get('Constants')(db)

    def _u(db_value):
        if db_value is None:
            return text_type('')
        if isinstance(db_value, bytes):
            return db_value.decode(db.encoding)
        return text_type(db_value)

    def _row_to_quar(row):
        """ list_entity_quarantines row to dict """
        return {
            'q_type': text_type(co.Quarantine(row['quarantine_type'])),
            'q_desc': _u(row['description']),
            'q_date': text_type(row['start_date'].strftime('%Y-%m-%d')),
        }

    logger.debug('caching personal accounts ...')
    owner_type = co.entity_person
    accounts = ac.search(owner_type=owner_type)
    logger.info('found %d accounts with owner_type=%r',
                len(accounts), text_type(owner_type))

    logger.debug('caching account homedirs ...')
    acc2disk = dict((r['account_id'], r['path'])
                    for r in ac.list_account_home())
    logger.info('found %d accounts assigned to a disk', len(acc2disk))

    logger.debug('caching active account quarantines ...')
    acc2quar = defaultdict(list)
    for q in ac.list_entity_quarantines(only_active=True,
                                        entity_types=co.entity_account):
        acc2quar[q['entity_id']].append(q)
    logger.info('found quarantines for %d accounts', len(acc2quar))

    logger.debug('caching person names ...')
    person2name = dict(
        (r['person_id'], r['name'])
        for r in pe.search_person_names(name_variant=co.name_full,
                                        source_system=co.system_cached))
    logger.info('found full names for %d persons', len(person2name))

    # Add person_id to the list if the person has an affiliation
    logger.debug('caching person affiliations ...')
    person_has_affs = set((r['person_id'] for r in pe.list_affiliations()))
    logger.info('found %d persons with affiliations', len(person_has_affs))

    for acc in accounts:
        # Is the account owner still affiliated?
        if acc['owner_id'] in person_has_affs:
            continue

        for quar in acc2quar[acc['account_id']]:
            if (quar['start_date'] + DateTimeDelta(365)) < now():
                break
        else:
            # loop terminated wihtout finding a 'quar' -- i.e. no active
            # quarantine older than one year
            continue

        yield {
            'account_name': _u(acc['name']),
            'full_name': _u(person2name.get(acc['owner_id'])) or u'(not set)',
            'disk_path': _u(acc2disk.get(acc['account_id'])) or u'(not set)',
            'q_type': text_type(co.Quarantine(quar['quarantine_type'])),
            'q_desc': _u(quar['description']),
            'q_date': text_type(quar['start_date'].strftime('%Y-%m-%d')),
        }


def aggregate(iterable, key):
    """ Take an iterable of dicts to output, and organize in groups.

    >>> aggregate([{'a': 'foo', 'b': 'x'}, {'a': 'foo', 'b': 'y'}], 'b')
    {'x': [{'a': 'foo', 'b': 'x'}], 'y': [{'a': 'foo', 'b': 'y'}]}

    """
    root = defaultdict(list)
    for item in iterable:
        root[item[key]].append(item)
    return dict(root)


def write_html_report(stream, codec, matches):
    output = codec.streamwriter(stream)
    template_env = Environment(trim_blocks=True, lstrip_blocks=True)
    report = template_env.from_string(template)

    num_accounts = sum(len(v) for v in matches.values())
    output.write(
        report.render({
            'encoding': codec.name,
            'num_accounts': num_accounts,
            'matches': matches,
            'when': now().strftime('%Y-%m-%d %H:%M:%S'),
        })
    )
    output.write('\n')


DEFAULT_ENCODING = 'utf-8'


def codec_type(encoding):
    try:
        return codecs.lookup(encoding)
    except LookupError as e:
        raise ValueError(str(e))


def main(inargs=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-o', '--output',
        metavar='FILE',
        type=argparse.FileType('w'),
        default='-',
        help='the file to print the report to, defaults to stdout')
    parser.add_argument(
        '-e', '--encoding',
        dest='codec',
        type=codec_type,
        default=DEFAULT_ENCODING,
        help="output file encoding, defaults to %(default)s")

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    # Initialization of database connection
    db = Factory.get('Database')()

    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %r", args)

    # Search for accounts
    matches = aggregate(get_matching_accs(db), 'disk_path')

    # Count number of accounts
    logger.info('Found %d matching accounts',
                sum(len(v) for v in matches.values()))

    write_html_report(args.output, args.codec, matches)

    args.output.flush()
    if args.output is not sys.stdout:
        args.output.close()

    logger.info('Report written to %s', args.output.name)
    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
