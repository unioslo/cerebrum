#!/usr/bin/env python
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
""" Generate an HTML report over persons with multiple accounts.

This script generates an HTML report over persons in Cerberum with multiple
accounts, and optionally sends out a report over matching person_ids by email.

The HTML report is organized by faculty and OU.
"""
import argparse
import collections
import datetime
import logging
import sys

import jinja2
import six

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import codec_type, get_constant
from Cerebrum.utils.email import sendmail
from Cerebrum.utils.funcwrap import memoize


logger = logging.getLogger(__name__)
now = datetime.datetime.now

# TODO: Move to actual template, or at least use a base template
template = u"""
<!DOCTYPE html>
<html>
  <head>
    <meta charset="{{ encoding | default('utf-8') }}" />
    <title>Active accounts report</title>
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
      {{ stats.matches }} have more than {{ settings.minimum }} accounts
      {% if settings.maximum %}and less than {{ settings.maximum }}
      accounts{% endif %}.
    </p>

    {% for fac_group in data
        | groupby('faculty_sko')
        | sort(attribute='grouper') %}
    <h1>{{ fac_group.grouper }} - {{ fac_group.list[0]['faculty_name'] }}</h1>

    {% for ou_group in fac_group.list
        | groupby('ou_sko')
        | sort(attribute='grouper') %}
    <h2>{{ ou_group.grouper }} - {{ ou_group.list[0]['ou_name'] }}</h2>
    <table>
      <thead>
        <tr>
          <th>Name</th>
          <th>Employee ID</th>
          <th>Number of users</th>
          <th>Usernames</th>
        </tr>
      </thead>
      {% for item in ou_group.list %}
      <tr>
        <td>{{ item.person_name }}</td>
        <td>{{ item.sap_id }}</td>
        <td>{{ item.accounts | count }}</td>
        <td>{{ item.accounts | join(', ') }}</td>
      </tr>
      {% endfor %}
    </table>

    {% endfor %}

    {% endfor %}

    <p class="meta">
      Generated: {{ when }}
    </p>
  </body>
</html>
""".strip()


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


def make_account_cache(db):
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    account_cache = collections.defaultdict(list)
    logger.debug('caching accounts...')
    for row in ac.search(owner_type=co.entity_person,
                         expire_start=None):
        account_cache[row['owner_id']].append(row['name'])
    logger.debug('cached accounts for %d persons', len(account_cache))

    def get_accounts(person_id):
        return account_cache[person_id]
    return get_accounts


def make_sapid_cache(db):
    co = Factory.get('Constants')(db)
    pe = Factory.get('Person')(db)
    extid_cache = dict()
    id_type = co.externalid_sap_ansattnr
    logger.debug('caching %s ids...', six.text_type(id_type))
    for r in pe.list_external_ids(id_type=id_type,
                                  entity_type=co.entity_person,
                                  source_system=co.system_sap):
        extid_cache[r['entity_id']] = r['external_id']
    logger.debug('cached sap id for %d persons', len(extid_cache))

    def get_sapid(person_id, default=None):
        return extid_cache.get(person_id, default)
    return get_sapid


def account_filter(accounts, minimum, maximum):
    if len(accounts) < minimum:
        return False
    if maximum and len(accounts) > maximum:
        return False
    return True


def get_person_ids(db):
    pe = Factory.get('Person')(db)
    for row in pe.list_persons():
        yield row['person_id']


def get_persons_by_sko(db, source_systems, minimum, maximum, stats=None):
    stats = dict if stats is None else stats
    stats.update({
        'persons': 0,
        'matches': 0,
    })
    co = Factory.get('Constants')(db)
    pe = Factory.get('Person')(db)
    ou = Factory.get('OU')(db)

    logger.debug('caching data...')

    get_person_name = make_name_cache(db)

    ou2sko = dict(
        (row['ou_id'], "%02d%02d%02d" % (row['fakultet'],
                                         row['institutt'],
                                         row['avdeling']))
        for row in ou.get_stedkoder())
    sko2name = dict(
        (ou2sko[row['entity_id']], row['name'])
        for row in ou.search_name_with_language(
                name_variant=co.ou_name_display,
                name_language=co.language_nb))

    get_sapid = make_sapid_cache(db)
    get_accounts = make_account_cache(db)

    logger.debug('fetching persons...')
    for person_id in get_person_ids(db):
        stats['persons'] += 1

        accounts = get_accounts(person_id)
        if not account_filter(accounts, minimum, maximum):
            continue

        name = get_person_name(person_id)
        sap_id = get_sapid(person_id)

        stats['matches'] += 1

        for row in pe.list_affiliations(person_id=person_id,
                                        source_system=source_systems):
            ou_id = row['ou_id']
            ou_sko = ou2sko[ou_id]
            ou_name = sko2name[ou_sko]
            faculty_sko = "%02s0000" % ou_sko[:2]
            faculty_name = sko2name.get(faculty_sko)

            yield {
                'person_id': person_id,
                'sap_id': sap_id,
                'person_name': name,
                'accounts': accounts,
                'ou_id': ou_id,
                'ou_sko': ou_sko,
                'ou_name': ou_name,
                'faculty_name': faculty_name,
                'faculty_sko': faculty_sko,
            }
    logger.info("Processed %(persons)d persons, found %(matches)d persons",
                stats)


def write_html_report(stream, codec, persons, stats, minimum, maximum):
    output = codec.streamwriter(stream)
    template_env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True)
    report = template_env.from_string(template)

    output.write(
        report.render({
            'encoding': codec.name,
            'settings': {
                'minimum': minimum,
                'maximum': maximum,
            },
            'stats': stats,
            'data': list(persons),
            'when': now().strftime('%Y-%m-%d %H:%M:%S'),
        })
    )
    output.write('\n')


def make_email_report(persons, minimum, maximum, stats):
    report = 'Report over persons with at least {:d} accounts'.format(minimum)
    if maximum:
        report += ' and at most {:d} accounts'.format(maximum)
    report += ' in Cerebrum:\n\nperson_id\n'
    report += '\n'.join(str(p['person_id']) for p in persons)
    report += '\n'
    return report


DEFAULT_ENCODING = 'utf-8'
DEFAULT_SOURCE = 'SAP,FS'


def main(inargs=None):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__)
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

    parser.add_argument(
        '--min',
        dest='minimum',
        type=lambda x: abs(int(x)),
        default=1,
        metavar='MIN',
        help='Report persons with more than %(metavar)s users'
             ' (default: %(default)s)')
    parser.add_argument(
        '--max',
        dest='maximum',
        type=lambda x: abs(int(x)),
        default=None,
        metavar='MAX',
        help='Report persons with less than %(metavar)s users'
             ' (default: no limit)')

    source_arg = parser.add_argument(
        '--source_systems',
        default=DEFAULT_SOURCE,
        help="comma separated list of source systems to search through,"
             " defaults to %(default)s")

    mail_to_arg = parser.add_argument(
        '-t', '--mail-to',
        dest='mail_to',
        metavar='ADDR',
        help="Send an email report to %(metavar)s")
    mail_from_arg = parser.add_argument(
        '-f', '--mail-from',
        dest='mail_from',
        metavar='ADDR',
        help="Send reports from %(metavar)s")

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    # Require mail_to and mail_from, or neither
    if bool(args.mail_from) ^ bool(args.mail_to):
        apply_to = mail_to_arg if args.mail_to else mail_from_arg
        missing = mail_from_arg if args.mail_to else mail_to_arg
        parser.error(argparse.ArgumentError(
            apply_to,
            "Must set {0} as well".format('/'.join(missing.option_strings))))

    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)

    src = [get_constant(db, parser, co.AuthoritativeSystem, code, source_arg)
           for code in args.source_systems.split(',')]

    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %r", args)
    logger.debug("source_systems: %r", src)

    stats = collections.defaultdict(int)
    persons = list(get_persons_by_sko(db, src, args.minimum, args.maximum,
                                      stats))

    write_html_report(args.output, args.codec, persons, stats, args.minimum,
                      args.maximum)

    if args.mail_to:
        subject = "Report from %s" % parser.prog
        body = make_email_report(persons, args.minimum, args.maximum, stats)
        logger.debug('Sending report to %r (%r)', args.mail_to, subject)
        sendmail(args.mail_to, args.mail_from, subject, body)

    args.output.flush()
    if args.output is not sys.stdout:
        args.output.close()

    logger.info('Report written to %s', args.output.name)
    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
