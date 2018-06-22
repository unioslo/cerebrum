#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2011-2018 University of Oslo, Norway
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
""" Generate an HTML report with quarantined accounts on employee disks. """

import argparse
import logging
import sys
from collections import defaultdict

from jinja2 import Environment
from mx.DateTime import now, ISO, RelativeDateTime
from six import text_type

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Entity import EntitySpread
from Cerebrum.Utils import Factory
from Cerebrum.modules.EntityTrait import EntityTrait
from Cerebrum.utils.funcwrap import memoize
from Cerebrum.utils.argutils import codec_type


logger = logging.getLogger(__name__)


# TODO: Move to actual template, or at least use a base template
template = u"""
<!DOCTYPE html>
<html>
  <head>
    <meta http-equiv="Content-Type"
          content="text/html; charset={{ encoding | default('utf-8') }}">
    <title>Quarantines</title>
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
      {{ num_quarantines }} quarantines older than {{ start_date }}
    </p>

    {% for group in quarantines | groupby('ou') | sort(attribute='grouper') %}

    {% if loop.changed(group.list[0]['faculty']) %}
    <h1>{{ group.list[0]['faculty'] }}</h1>
    {% endif %}

    <h2>{{ group.grouper }}</h2>
    <table>
      <thead>
        <tr>
          <th>Name</th>
          <th>Affiliation</th>
          <th>Username</th>
          <th>Quarantine start</th>
          <th>Quarantine type</th>
        </tr>
      </thead>

    {% for item in group.list | sort(attribute='account_name') %}
      <tr>
        <td>{{ item.person_name }}</td>
        <td>{{ item.status }}</td>
        <td>{{ item.account_name }}</td>
        <td>{{ item.q_date }}</td>
        <td>{{ item.q_type }}</td>
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


def get_student_disks(db):
    """ Get disks tagged as student disks. """
    et = EntityTrait(db)
    co = Factory.get('Constants')(db)
    return set(
        t['entity_id']
        for t in et.list_traits(code=co.trait_student_disk))


def get_enabled_accounts(db):
    """ Get accounts with spreads.

    Accounts with spreads will not be considered `Account.is_deleted()` or
    `Account.is_reserved()`.
    """
    es = EntitySpread(db)
    co = Factory.get('Constants')(db)
    return set(e_id for e_id, s_code in
               es.list_all_with_spread(entity_types=co.entity_account))


def make_name_cache(db):
    pe = Factory.get('Person')(db)
    co = Factory.get('Constants')(db)

    @memoize
    def get_name(person_id):
        res = pe.search_person_names(
            person_id=person_id,
            source_system=co.system_cached,
            name_variant=co.name_full)
        return (res or [{'name': None}])[0]['name']
    return get_name


def make_affiliation_cache(db):
    pe = Factory.get(b'Person')(db)
    co = Factory.get('Constants')(db)

    @memoize
    def get_affiliations(person_id):
        pe.clear()
        pe.find(person_id)
        affs = tuple(dict(a) for a in pe.get_affiliations())
        for a in affs:
            a['affiliation'] = co.PersonAffiliation(a['affiliation'])
            a['status'] = co.PersonAffStatus(a['status'])
            a['source_system'] = co.AuthoritativeSystem(a['source_system'])
        return tuple(affs)
    return get_affiliations


def get_quarantine_data(db, start_date):
    """ Get quarantines. """
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    ou = Factory.get('OU')(db)

    def _u(db_value):
        if isinstance(db_value, bytes):
            return db_value.decode(db.encoding)
        return db_value

    # person info lookup
    get_person_name = make_name_cache(db)
    get_person_affiliations = make_affiliation_cache(db)

    # ou info cache
    ou2sko = dict(
        (row['ou_id'], ("%02d%02d%02d" % (row['fakultet'],
                                          row['institutt'],
                                          row['avdeling'])))
        for row in ou.get_stedkoder())

    sko2name = dict(
        (ou2sko[row['entity_id']], row['name'])
        for row in ou.search_name_with_language(
                name_variant=co.ou_name_display,
                name_language=co.language_nb))

    # account info cache
    accounts = dict(
        (r['account_id'], r)
        for r in ac.search(owner_type=co.entity_person,
                           expire_start=None))
    logger.debug('cached %d personal accounts', len(accounts))

    enabled_accounts = get_enabled_accounts(db)
    logger.debug('identified %d enabled accounts', len(enabled_accounts))

    # disk/homedir cache
    account_home = defaultdict(set)
    for row in ac.list_account_home():
        account_home[row['account_id']].add(row['disk_id'])
    logger.debug('cached homedir disk_id for %d accounts', len(account_home))

    student_disks = get_student_disks(db)
    logger.debug('identified %d student disks', len(student_disks))

    quarantine_list = ac.list_entity_quarantines(
        entity_types=co.entity_account,
        only_active=True)

    logger.info('%d quarantines to process', len(quarantine_list))

    stats = {
        'skip_student_disk': 0,
        'skip_disabled': 0,
        'skip_non_personal': 0,
        'skip_too_recent': 0,
        'include': 0,
    }

    for i, row_qua in enumerate(quarantine_list):

        if i and i % 50000 == 0:
            logger.debug('... %d processed, %d found', i, stats['include'])

        if row_qua['start_date'] > start_date:
            stats['skip_too_recent'] += 1
            continue  # quarantine is not old enough, skip

        account_id = row_qua['entity_id']

        if account_id not in accounts:
            stats['skip_non_personal'] += 1
            continue  # Filter out non-personal accounts.

        if account_id not in enabled_accounts:
            stats['skip_disabled'] += 1
            continue

        if all(disk_id in student_disks
               for disk_id in account_home[account_id]):
            stats['skip_student_disk'] += 1
            continue  # disk_id refers to a student disk, skip.

        account_name = accounts[account_id]['name']
        owner_id = accounts[account_id]['owner_id']
        name = get_person_name(owner_id)
        affiliations = get_person_affiliations(owner_id)

        data = {
            'account_id': account_id,
            'person_id': owner_id,
            'person_name': _u(name),
            'account_name': _u(account_name),
            'q_type': text_type(co.Quarantine(row_qua['quarantine_type'])),
            'q_date': text_type(row_qua['start_date'].strftime('%Y-%m-%d')),
            'status': None,
            'ou': 'Uregistrert',
            'faculty': 'Uregistrert',
        }

        if not affiliations:
            yield dict(data)

        for row in affiliations:
            sko = ou2sko[row['ou_id']]
            fak = sko[:2] + "0000"

            data.update({
                'status': text_type(row['status']),
                'ou': u' - '.join((text_type(sko), _u(sko2name.get(sko, '')))),
                'faculty': _u(sko2name.get(fak, '')) or text_type(fak),
            })
            yield dict(data)

        stats['include'] += 1

    logger.debug('... done processing quarantines')

    logger.info('Got %d quarantines', stats['include'])
    logger.info('Skipped %d quarantines',
                sum(stats.values()) - stats['include'])
    logger.debug('Skipped %d quaranintes started after %s',
                 stats['skip_too_recent'], start_date.strftime('%Y-%m-%d'))
    logger.debug('Skipped %d quarantines on deleted and reserved accounts',
                 stats['skip_disabled'])
    logger.debug('Skipped %d quarantines on non-personal accounts',
                 stats['skip_non_personal'])
    logger.debug('Skipped %d quarantines on accounts on students disks',
                 stats['skip_student_disk'])


def write_html_report(stream, codec, quarantines, start_date):
    output = codec.streamwriter(stream)
    template_env = Environment(trim_blocks=True, lstrip_blocks=True)
    report = template_env.from_string(template)

    num_quarantines = len(set((q['q_type'], q['account_id'])
                              for q in quarantines))

    output.write(
        report.render({
            'encoding': codec.name,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'num_quarantines': num_quarantines,
            'quarantines': quarantines,
            'when': now().strftime('%Y-%m-%d %H:%M:%S'),
        })
    )
    output.write('\n')


DEFAULT_ENCODING = 'utf-8'


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Generate an html formatted report of accounts with"
                    " active quarantines")

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

    age_arg = parser.add_mutually_exclusive_group(required=True)
    age_arg.add_argument(
        '-s', '--start_date',
        metavar='DATE',
        dest='start_date',
        type=ISO.ParseDate,
        help='Report quarantines set by date (YYYY-MM-DD)')
    age_arg.add_argument(
        '-a', '--age',
        metavar='DAYS',
        dest='start_date',
        type=lambda x: now() + RelativeDateTime(days=-abs(int(x))),
        help='Report quarantines set by age (in days)')

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    db = Factory.get('Database')()

    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %r", args)

    quarantines = list(get_quarantine_data(db, args.start_date))

    write_html_report(args.output, args.codec, quarantines, args.start_date)

    args.output.flush()
    if args.output is not sys.stdout:
        args.output.close()

    logger.info('Report written to %s', args.output.name)
    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
