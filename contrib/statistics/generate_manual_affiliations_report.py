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
import os
import sys

from jinja2 import Environment, FileSystemLoader, PackageLoader

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
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
    ou = Factory.get('OU')(db)
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
        const.affiliation_manuell_cicero,  # MANUELL/cicero
        const.affiliation_manuell_ekst_person,  # MANUELL/ekst_person
        const.affiliation_manuell_gjest,  # MANUELL/gjest
        const.affiliation_manuell_gjesteforsker,  # MANUELL/gjesteforsker
        const.affiliation_manuell_inaktiv_ansatt,  # MANUELL/inaktiv_ansatt
        const.affiliation_manuell_inaktiv_student,  # MANUELL/inaktiv_student
        const.affiliation_manuell_konsulent,  # MANUELL/konsulent
        const.affiliation_manuell_radium,  # MANUELL/radium
        const.affiliation_manuell_frisch,  # MANUELL/frisch
        const.affiliation_manuell_unirand  # MANUELL/unirand
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
             const.PersonAffStatus(aff['status'])) for aff in
            person.get_affiliations()]
        person_affiliations_str = list()
        for paff_row in person_affiliations:
            if (
                    (paff_row[0] in EXEMPT_AFFILIATIONS) or
                    (paff_row[1] in EXEMPT_AFFILIATION_STATUSES)
            ):
                has_exempted = True
                break
            person_affiliations_str.append(str(paff_row[1]))
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
                ou.clear()
                ou.find(row['ou_id'])
                account_affiliations.append('{affiliation}@{ou}'.format(
                    affiliation=const.PersonAffiliation(
                        row['affiliation']),
                    ou=_format_ou_name(ou, const)))
            if not account_affiliations:
                break  # all affiliations are in EXEMPT_AFFILIATIONS
            manual_users.append({
                'account_name': account.account_name.decode('latin1'),
                'account_affiliations': str(
                    account_affiliations).decode('utf-8'),
                'person_name': person.get_name(
                    const.system_cached,
                    getattr(
                        const, cereconf.DEFAULT_GECOS_NAME)).decode('latin1'),
                'person_affiliations': str(
                    person_affiliations_str).decode('latin1')})
    sorted_manual_users = sorted(manual_users,
                                 key=lambda x: x['account_affiliations'])
    summary = (u'{0} accounts for {1} persons of total {2} '
               u'persons processed').format(
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
            ('account_affiliations', u'Account affiliations'),
            ('account_name', u'Account name'),
            ('person_name', u'Name'),
            ('person_affiliations', u'Persont affiliations')),
        title=u'Manual affiliations report',
        prelist=u'<h3>Manual affiliations report</h3>',
        postlist=u'<p>{summary}</p>'.format(summary=summary),
        items=sorted_manual_users).encode('utf-8')
    if args.output:
        with open(args.output, 'w') as fp:
            fp.write(output_str)
    else:
        sys.stdout.write(output_str)
    logger.info('{script_name} finished'.format(script_name=sys.argv[0]))
    sys.exit(0)


if __name__ == '__main__':
    main()
