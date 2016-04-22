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
import collections

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
    parser.add_argument('-l', '--logger-name',
                        dest='logname',
                        default='cronjob',
                        help='Specify logger (default: cronjob).')
    args = parser.parse_args()

    db = Factory.get('Database')()
    person = Factory.get('Person')(db)
    const = Factory.get('Constants')(db)
    account = Factory.get('Account')(db)
    ou = Factory.get('OU')(db)

    total_person_count = 0
    person_count = 0

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
        const.affiliation_manuell_unirand  # MANUELL/unirand
    ]
    manual_users = dict()

    for person_row in person.list_affiliated_persons(
            aff_list=EXEMPT_AFFILIATIONS,
            status_list=EXEMPT_AFFILIATION_STATUSES,
            inverted=True):
        person.clear()
        total_person_count += 1
        person.find(person_row['person_id'])
        affiliations = [str(const.PersonAffStatus(
            aff['status'])) for aff in person.get_affiliations()]
        accounts = person.get_accounts()
        if accounts:
            person_count += 1
        for account_row in accounts:
            account.clear()
            account.find(account_row['account_id'])
            account_affiliations = list()
            for row in account.get_account_types(filter_expired=False):
                if const.PersonAffiliation(
                        row['affiliation']) not in EXEMPT_AFFILIATIONS:
                    ou.clear()
                    ou.find(row['ou_id'])
                    account_affiliations.append('{affiliation}@{ou}'.format(
                        affiliation=const.PersonAffiliation(
                            row['affiliation']),
                        ou=_format_ou_name(ou, const)))
            if not account_affiliations:
                break  # all affiliations are in EXEMPT_AFFILIATIONS
            fields = '{account_affiliations} - {person_affiliations}'.format(
                account_affiliations=account_affiliations,
                person_affiliations=str(affiliations))
            manual_users[account.account_name] = fields
    ordered_manual_users = collections.OrderedDict(
        sorted(manual_users.items(),
               key=lambda x: x[0]))
    for key, value in ordered_manual_users.items():
        print('{username}: {fields}'.format(username=key, fields=value))
    print('{0} accounts for {1} persons of total {2} persons processed'.format(
        len(manual_users),
        person_count,
        total_person_count))


if __name__ == '__main__':
    main()
