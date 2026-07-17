#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016-2024 University of Oslo, Norway
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
""" Generate an HTML or CSV report with manual affiliations.

This program reports on persons with affiliation in the MANUAL source system.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import datetime
import logging
import os

import six
from jinja2 import Environment, FileSystemLoader

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.Stedkode import OuCache
from Cerebrum.utils import csvutils
from Cerebrum.utils import file_stream
from Cerebrum.utils.argutils import codec_type

logger = logging.getLogger(__name__)
now = datetime.datetime.now


def get_manual_users(db, stats=None, ignore_quarantined=False):

    if stats is None:
        stats = dict()

    stats.update({
        'total_person_count': 0,
        'person_count': 0,
        'manual_count': 0,
    })

    db = Factory.get('Database')()
    person = Factory.get('Person')(db)
    const = Factory.get('Constants')(db)
    account = Factory.get('Account')(db)

    def _u(db_value):
        if db_value is None:
            return six.text_type('')
        if isinstance(db_value, bytes):
            return db_value.decode(db.encoding)
        return six.text_type(db_value)

    ou_cache = OuCache(db)

    # TODO: Dynamic exemptions
    # TODO: Is this right?  This excludes *everyone* at UiO?
    exempt_affiliations = [
        const.affiliation_ansatt,  # ANSATT
        const.affiliation_student,  # STUDENT
        const.affiliation_tilknyttet  # TILKNYTTET
    ]
    exempt_affiliation_statuses = [
        const.affiliation_manuell_ekstern,  # MANUELL/ekstern
        const.affiliation_manuell_alumni  # MANUELL/alumni
    ]

    # TODO: Should probably build lookup tables for accounts and quarantines,
    # rather than doing new db-lookups per row

    for person_row in person.list_affiliated_persons(
            aff_list=exempt_affiliations,
            status_list=exempt_affiliation_statuses,
            inverted=True):

        person.clear()
        stats['total_person_count'] += 1
        person.find(person_row['person_id'])
        has_exempted = False
        person_affiliations = [(const.PersonAffiliation(aff['affiliation']),
                                const.PersonAffStatus(aff['status']),
                                aff['ou_id'])
                               for aff in person.get_affiliations()]
        person_affiliations_list = list()
        person_ou_list = list()
        for paff_row in person_affiliations:
            if (
                    paff_row[0] in exempt_affiliations
                    or paff_row[1] in exempt_affiliation_statuses
            ):
                has_exempted = True
                break
            person_ou_list.append(ou_cache.format_ou(paff_row[2]))
            person_affiliations_list.append(six.text_type(paff_row[1]))

        if has_exempted:
            # This person has at least one exempted affiliation / status
            # We ignore this person
            continue

        accounts = person.get_accounts()
        if accounts:
            stats['person_count'] += 1

        for account_row in accounts:
            account.clear()
            account.find(account_row['account_id'])
            account_affiliations = list()
            for row in account.get_account_types(filter_expired=False):
                account_affiliations.append(
                    u'{affiliation}@{ou}'.format(
                        affiliation=six.text_type(
                            const.PersonAffiliation(row['affiliation'])),
                        ou=ou_cache.format_ou(row['ou_id'])))
            if not account_affiliations:
                account_affiliations.append('EMPTY')
            quarantines = [
                six.text_type(const.Quarantine(q['quarantine_type']))
                for q in account.get_entity_quarantine(only_active=True)
            ]
            if ignore_quarantined and quarantines:
                continue

            # jinja2 accepts only unicode strings
            stats['manual_count'] += 1
            yield {
                'account_name': _u(account.account_name),
                'account_affiliations': ', '.join(account_affiliations),
                'account_quarantines': ', '.join(quarantines),
                'person_name': _u(
                    person.get_name(
                        const.system_cached,
                        getattr(const, cereconf.DEFAULT_GECOS_NAME))),
                'person_ou_list': ', '.join(person_ou_list),
                'person_affiliations': ', '.join(person_affiliations_list),
            }

    logger.info('%(manual_count)d accounts for %(total_person_count)d persons'
                ' of total %(person_count)d persons processed', stats)


def write_csv_report(stream, encoding, users):
    """ Write a CSV report to an open bytestream. """
    # number_of_users = sum(len(users) for users in no_aff.values())

    stream.write('# Encoding: %s\n' % (encoding,))
    stream.write('# Generated: %s\n' % now().strftime('%Y-%m-%d %H:%M:%S'))
    # output.write('# Number of users found: %d\n' % number_of_users)
    fields = ['person_ou_list', 'person_affiliations', 'person_name',
              'account_name', 'account_affiliations', 'account_quarantines']

    writer = csvutils.UnicodeDictWriter(stream, fields,
                                        dialect=csvutils.CerebrumDialect)
    writer.writeheader()
    writer.writerows(users)


def write_html_report(stream, users, summary):
    """ Write an HTML report to an open bytestream. """
    template_path = os.path.join(os.path.dirname(__file__), 'templates')
    env = Environment(loader=FileSystemLoader(template_path))
    template = env.get_template('simple_list_overview.html')

    stream.write(
        template.render({
            'headers': (
                ('person_ou_list', 'Person OU list'),
                ('person_affiliations', 'Persont affiliations'),
                ('person_name', 'Name'),
                ('account_name', 'Account name'),
                ('account_affiliations', 'Account affiliations')),
            'title': 'Manual affiliations report ({})'.format(
                now().strftime('%Y-%m-%d %H:%M:%S')),
            'prelist': '<h3>Manual affiliations report</h3>',
            'postlist': '<p>{}</p>'.format(summary),
            'items': users,
        })
    )
    stream.write('\n')


DEFAULT_ENCODING = 'utf-8'


def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-o', '--output',
        metavar='FILE',
        default=file_stream.DEFAULT_STDOUT_NAME,
        help="write html output to %(metavar)s (default: stdout)",
    )
    parser.add_argument(
        '-e', '--output-encoding',
        dest='codec',
        default=DEFAULT_ENCODING,
        type=codec_type,
        help="output file encoding, defaults to %(default)s",
    )
    parser.add_argument(
        '--csv',
        metavar='FILE',
        default=None,
        help="write csv output to %(metavar)s, if needed",
    )
    parser.add_argument(
        '--csv-encoding',
        dest='csv_codec',
        default=DEFAULT_ENCODING,
        type=codec_type,
        help="output file encoding, defaults to %(default)s",
    )
    parser.add_argument(
        '--ignore-quarantined',
        dest='ignore_quarantined',
        action='store_true',
        help="Ignore quarantined accounts in report",
    )

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    db = Factory.get('Database')()

    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %s", repr(args))

    stats = dict()
    manual_users = get_manual_users(db, stats,
                                    ignore_quarantined=args.ignore_quarantined)

    sorted_manual_users = sorted(manual_users,
                                 key=lambda x: x['person_ou_list'])
    summary = ('{manual_count} accounts for {total_person_count} persons of'
               ' total {person_count} persons processed').format(**stats)

    html_filename = args.output
    html_encoding = args.codec.name
    with file_stream.get_output_context(html_filename,
                                        encoding=html_encoding) as f:
        write_html_report(f, sorted_manual_users, summary)
        logger.info('HTML report written to %s', f.name)

    if args.csv:
        csv_filename = args.csv
        csv_encoding = args.csv_codec.name
        with file_stream.get_output_context(csv_filename,
                                            encoding=csv_encoding) as f:
            write_csv_report(f, csv_encoding, sorted_manual_users)
            logger.info('CSV report written to %s', f.name)

    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
