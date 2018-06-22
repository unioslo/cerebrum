#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016-2018 University of Oslo, Norway
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

import argparse
import csv
import datetime
import logging
import os
import sys

from jinja2 import Environment, FileSystemLoader
from six import text_type

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
import Cerebrum.utils.csvutils as _csvutils
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import codec_type

logger = logging.getLogger(__name__)
now = datetime.datetime.now


class CsvDialect(csv.excel):
    """Specifying the CSV output dialect the script uses.

    See the module `csv` for a description of the settings.

    """
    delimiter = ';'
    lineterminator = '\n'


class OuCache(object):
    def __init__(self, db):
        co = Factory.get('Constants')(db)
        ou = Factory.get('OU')(db)

        self._ou2sko = dict(
            (row['ou_id'], (u"%02d%02d%02d" % (row['fakultet'],
                                               row['institutt'],
                                               row['avdeling'])))
            for row in ou.get_stedkoder())

        self._ou2name = dict(
            (row['entity_id'], row['name'])
            for row in ou.search_name_with_language(
                name_variant=co.ou_name_short,
                name_language=co.language_nb))

    def format_ou(self, ou_id):
        return u'{0} ({1})'.format(self._ou2sko[ou_id], self._ou2name[ou_id])


def get_manual_users(db, stats=None):

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
            return text_type('')
        if isinstance(db_value, bytes):
            return db_value.decode(db.encoding)
        return text_type(db_value)

    ou_cache = OuCache(db)

    # TODO: Dynamic exemptions
    EXEMPT_AFFILIATIONS = [
        const.affiliation_ansatt,  # ANSATT
        const.affiliation_student,  # STUDENT
        const.affiliation_tilknyttet  # TILKNYTTET
    ]
    EXEMPT_AFFILIATION_STATUSES = [
        const.affiliation_manuell_ekstern,  # MANUELL/ekstern
        const.affiliation_manuell_alumni  # MANUELL/alumni
    ]

    for person_row in person.list_affiliated_persons(
            aff_list=EXEMPT_AFFILIATIONS,
            status_list=EXEMPT_AFFILIATION_STATUSES,
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
                    paff_row[0] in EXEMPT_AFFILIATIONS
                    or paff_row[1] in EXEMPT_AFFILIATION_STATUSES
            ):
                has_exempted = True
                break
            person_ou_list.append(ou_cache.format_ou(paff_row[2]))
            person_affiliations_list.append(text_type(paff_row[1]))

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
                        affiliation=text_type(
                            const.PersonAffiliation(row['affiliation'])),
                        ou=ou_cache.format_ou(row['ou_id'])))
            if not account_affiliations:
                account_affiliations.append('EMPTY')

            # jinja2 accepts only unicode strings
            stats['manual_count'] += 1
            yield {
                'account_name': _u(account.account_name),
                'account_affiliations': ', '.join(account_affiliations),
                'person_name': _u(
                    person.get_name(
                        const.system_cached,
                        getattr(const, cereconf.DEFAULT_GECOS_NAME))),
                'person_ou_list': ', '.join(person_ou_list),
                'person_affiliations': ', '.join(person_affiliations_list),
            }

    logger.info('%(manual_count)d accounts for %(total_person_count)d persons'
                ' of total %(person_count)d persons processed', stats)


def write_csv_report(stream, codec, users):
    """ Write a CSV report to an open bytestream. """
    # number_of_users = sum(len(users) for users in no_aff.values())

    output = codec.streamwriter(stream)
    output.write('# Encoding: %s\n' % codec.name)
    output.write('# Generated: %s\n' % now().strftime('%Y-%m-%d %H:%M:%S'))
    # output.write('# Number of users found: %d\n' % number_of_users)
    fields = ['person_ou_list', 'person_affiliations', 'person_name',
              'account_name', 'account_affiliations']

    writer = _csvutils.UnicodeDictWriter(output, fields, dialect=CsvDialect)
    writer.writeheader()
    writer.writerows(users)


def write_html_report(stream, codec, users, summary):
    """ Write an HTML report to an open bytestream. """
    output = codec.streamwriter(stream)

    env = Environment(
        loader=FileSystemLoader(os.path.join(os.path.dirname(__file__),
                                             'templates')))
    template = env.get_template('simple_list_overview.html')

    output.write(
        template.render({
            'headers': (
                ('person_ou_list', u'Person OU list'),
                ('person_affiliations', u'Persont affiliations'),
                ('person_name', u'Name'),
                ('account_name', u'Account name'),
                ('account_affiliations', u'Account affiliations')),
            'title': u'Manual affiliations report ({})'.format(
                now().strftime('%Y-%m-%d %H:%M:%S')),
            'prelist': u'<h3>Manual affiliations report</h3>',
            'postlist': u'<p>{}</p>'.format(summary),
            'items': users,
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
        help='output file for html report, defaults to stdout')
    parser.add_argument(
        '-e', '--output-encoding',
        dest='codec',
        default=DEFAULT_ENCODING,
        type=codec_type,
        help="output file encoding, defaults to %(default)s")

    parser.add_argument(
        '--csv',
        metavar='FILE',
        type=argparse.FileType('w'),
        default=None,
        help='output file for csv report, if needed')
    parser.add_argument(
        '--csv-encoding',
        dest='csv_codec',
        default=DEFAULT_ENCODING,
        type=codec_type,
        help="output file encoding, defaults to %(default)s")

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    db = Factory.get('Database')()

    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %r", args)

    stats = dict()
    manual_users = get_manual_users(db, stats)

    sorted_manual_users = sorted(manual_users,
                                 key=lambda x: x['person_ou_list'])
    summary = ('{manual_count} accounts for {total_person_count} persons of'
               ' total {person_count} persons processed').format(**stats)
    write_html_report(args.output, args.codec, sorted_manual_users, summary)

    args.output.flush()
    if args.output is not sys.stdout:
        args.output.close()
    logger.info('HTML report written to %s', args.output.name)

    if args.csv:
        write_csv_report(args.csv, args.csv_codec, sorted_manual_users)
        args.csv.flush()
        if args.csv is not sys.stdout:
            args.csv.close()
        logger.info('CSV report written to %s', args.csv.name)

    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
