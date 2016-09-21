#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2016 University of Oslo, Norway
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
import cStringIO
import codecs
import copy
import csv
import datetime
import os
import sys

from jinja2 import Environment, FileSystemLoader

import cereconf

from Cerebrum.Utils import Factory


def _format_ou_name(ou, const):
    short_name = ou.get_name_with_language(
        name_variant=const.ou_name_short,
        name_language=const.language_nb,
        default="")
    return "%02i%02i%02i (%s)" % (ou.fakultet,
                                  ou.institutt,
                                  ou.avdeling,
                                  short_name)


class UnicodeWriter(object):
    """
    A CSV writer which will write dict-rows to CSV file "f",
    which is encoded in the given encoding.

    Inspired by: https://docs.python.org/2.7/library/csv.html#module-csv
    """
    def __init__(self,
                 f,
                 dialect=csv.excel,
                 encoding='utf-8',
                 fieldnames=None,
                 **kwds):
        # Redirect output to a queue
        self.queue = cStringIO.StringIO()
        self.writer = csv.DictWriter(self.queue,
                                     dialect=dialect,
                                     fieldnames=fieldnames,
                                     **kwds)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writeheader(self):
        # Unicode headers are not supported here
        self.writer.writeheader()

    def writerow(self, row):
        row = copy.copy(row)  # do not ruine the original dict
        for key in row.keys():
            if isinstance(row[key], unicode):
                row[key] = row[key].encode('utf-8')
        self.writer.writerow(row)
        # self.writer.writerow([s.encode('utf-8') for s in row])
        # Fetch UTF-8 output from the queue ...
        data = self.queue.getvalue()
        data = data.decode('utf-8')
        # ... and reencode it into the target encoding
        data = self.encoder.encode(data)
        # write to the target stream
        self.stream.write(data)
        # empty queue
        self.queue.truncate(0)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


class CustomCSVDialect(csv.excel):
    """
    """
    delimiter = ';'
    lineterminator = '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--csv',
        type=str,
        dest='csv',
        default='',
        help=('The CSV-file to print the report to. '
              'Default: Do not generate CSV file.'))
    parser.add_argument(
        '-l', '--logger-name',
        dest='logname',
        type=str,
        default='cronjob',
        help='Specify logger (default: cronjob).')
    parser.add_argument(
        '-o', '--output',
        type=str,
        dest='output',
        default='',
        help='The file to print the report to. Defaults to stdout.')
    args = parser.parse_args()

    db = Factory.get('Database')()
    person = Factory.get('Person')(db)
    const = Factory.get('Constants')(db)
    account = Factory.get('Account')(db)
    person_ou = Factory.get('OU')(db)
    account_ou = Factory.get('OU')(db)
    logger = Factory.get_logger(args.logname)
    total_person_count = 0
    person_count = 0

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

    manual_users = list()
    logger.info('{script_name} started'.format(script_name=sys.argv[0]))
    for person_row in person.list_affiliated_persons(
            aff_list=EXEMPT_AFFILIATIONS,
            status_list=EXEMPT_AFFILIATION_STATUSES,
            inverted=True):
        person.clear()
        total_person_count += 1
        person.find(person_row['person_id'])
        has_exempted = False
        person_affiliations = [
            (const.PersonAffiliation(aff['affiliation']),
             const.PersonAffStatus(aff['status']),
             aff['ou_id']) for aff in
            person.get_affiliations()]
        person_affiliations_list = list()
        person_ou_list = list()
        for paff_row in person_affiliations:
            if (
                    (paff_row[0] in EXEMPT_AFFILIATIONS) or
                    (paff_row[1] in EXEMPT_AFFILIATION_STATUSES)
            ):
                has_exempted = True
                break
            person_ou.clear()
            person_ou.find(paff_row[2])
            person_ou_list.append(_format_ou_name(person_ou, const))
            person_affiliations_list.append(str(paff_row[1]))
        if has_exempted:
            # This person has at least one exempted affiliation / status
            # We ignore this person
            continue
        accounts = person.get_accounts()
        if accounts:
            person_count += 1
        for account_row in accounts:
            account.clear()
            account.find(account_row['account_id'])
            account_affiliations = list()
            for row in account.get_account_types(filter_expired=False):
                account_ou.clear()
                account_ou.find(row['ou_id'])
                account_affiliations.append('{affiliation}@{ou}'.format(
                    affiliation=const.PersonAffiliation(
                        row['affiliation']),
                    ou=_format_ou_name(account_ou, const)))
            if not account_affiliations:
                account_affiliations.append('EMPTY')
            # jinja2 accepts only unicode strings
            manual_users.append({
                'account_name': account.account_name.decode('latin1'),
                'account_affiliations': str(
                    account_affiliations).decode('utf-8'),
                'person_name': person.get_name(
                    const.system_cached,
                    getattr(
                        const, cereconf.DEFAULT_GECOS_NAME)).decode('latin1'),
                'person_ou_list': str(person_ou_list).decode('latin1'),
                'person_affiliations': str(
                    person_affiliations_list).decode('latin1')})
    sorted_manual_users = sorted(manual_users,
                                 key=lambda x: x['person_ou_list'])
    iso_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    summary = (u'{0}: {1} accounts for {2} persons of total {3} '
               u'persons processed').format(
                   iso_timestamp,
                   len(manual_users),
                   person_count,
                   total_person_count)
    logger.info(summary)
    env = Environment(
        loader=FileSystemLoader(os.path.join(os.path.dirname(__file__),
                                             'templates')))
    template = env.get_template('simple_list_overview.html')
    output_str = template.render(
        headers=(
            ('person_ou_list', u'Person OU list'),
            ('person_affiliations', u'Persont affiliations'),
            ('person_name', u'Name'),
            ('account_name', u'Account name'),
            ('account_affiliations', u'Account affiliations')),
        title=u'Manual affiliations report ({timestamp})'.format(
            timestamp=iso_timestamp),
        prelist=u'<h3>Manual affiliations report</h3>',
        postlist=u'<p>{summary}</p>'.format(summary=summary),
        items=sorted_manual_users).encode('utf-8')
    if args.output:
        with open(args.output, 'w') as fp:
            fp.write(output_str)
    else:
        sys.stdout.write(output_str)
    if args.csv:
        with open(args.csv, 'w') as fp:
            writer = UnicodeWriter(fp,
                                   encoding='utf-8',
                                   fieldnames=['person_ou_list',
                                               'person_affiliations',
                                               'person_name',
                                               'account_name',
                                               'account_affiliations'],
                                   dialect=CustomCSVDialect)
            writer.writeheader()
            writer.writerows(sorted_manual_users)
    logger.info('{script_name} finished'.format(script_name=sys.argv[0]))
    sys.exit(0)


if __name__ == '__main__':
    main()
