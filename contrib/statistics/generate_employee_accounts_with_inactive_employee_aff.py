#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2017 University of Oslo, Norway
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

from __future__ import unicode_literals, absolute_import, print_function

import argparse
import datetime
import os
import sys
import jinja2

import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.utils.funcwrap import memoize

logger = Factory.get_logger('cronjob')

db = Factory.get(b'Database')()
co = Factory.get(b'Constants')(db)
ac = Factory.get(b'Account')(db)
pe = Factory.get(b'Person')(db)
ou = Factory.get(b'OU')(db)


def get_mismatches():
    accounts = ac.list_accounts_by_type(affiliation=co.affiliation_ansatt)
    for acc in accounts:
        ac.clear()
        ac.find(acc['account_id'])
        if ac.owner_type != co.entity_person:
            continue
        pe.clear()
        pe.find(ac.owner_id)
        pe_affs = [(row['affiliation'], row['ou_id'])
                   for row in pe.get_affiliations()]
        if not pe_affs:
            continue
        ac_types = [(row['affiliation'], row['ou_id'])
                    for row in ac.get_account_types()
                    if row['affiliation'] == co.affiliation_ansatt]
        mismatch = [row for row in ac_types if row not in pe_affs]
        if not mismatch:
            continue
        yield (
            ('account_name', ac.account_name),
            ('person_id', pe.entity_id),
            ('account_types', format_affs(ac_types)),
            ('person_affiliations', format_affs(pe_affs)),
            ('mismatch', format_affs(mismatch)),
        )


@memoize
def format_ou(ou_id):
    ou.clear()
    ou.find(ou_id)
    return "{:02d}{:02d}{:02d}".format(ou.fakultet, ou.institutt, ou.avdeling)


def format_affs(affs):
    return ', '.join([
        "{}@{}".format(co.PersonAffiliation(aff), format_ou(ou_id))
        for aff, ou_id in affs])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-o', '--output',
        type=str,
        dest='output',
        default='',
        help='The file to print the report to. Defaults to stdout.')
    args = parser.parse_args()

    logger.info('{script_name} starting'.format(script_name=sys.argv[0]))

    accounts = [dict(x) for x in set(get_mismatches())]
    sorted_accounts = sorted(accounts,
                             key=lambda x: (x['person_id'],
                                            x['account_name']))
    logger.info('Found {} accounts with mismatches'.format(
        len(sorted_accounts)))

    iso_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    summary = []
    summary.append(
        'This report find accounts with at least one ANSATT affiliation and '
        'checks whether it\'s still valid.')
    summary.append('Accounts owned by a person with no affiliations '
                   'of any kind are ignored.')
    summary.append('{0}: Found {1} accounts'.format(
                   iso_timestamp,
                   len(sorted_accounts)))
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(
            os.path.join(os.path.dirname(__file__),
                         'templates')))
    template = env.get_template('simple_list_overview.html')
    output = template.render(
        headers=(
            ('person_id', 'Person entity ID'),
            ('account_name', 'Account name'),
            ('account_types', 'Account ANSATT affs'),
            ('person_affiliations', 'All person affs'),
            ('mismatch', 'Account ANSATT affs missing from person'),
            ),
        title='Employee accounts with an inactive ANSATT affiliation ({timestamp})'.format(
            timestamp=iso_timestamp),
        prelist='<h3>Employee accounts with an inactive ANSATT affiliation</h3>' +
                ''.join(['<p>{}</p>'.format(x) for x in summary]),
        items=sorted_accounts).encode('utf-8')
    if args.output:
        with open(args.output, 'w') as fp:
            fp.write(output)
    else:
        sys.stdout.write(output)
    logger.info('{script_name} finished'.format(script_name=sys.argv[0]))

if __name__ == '__main__':
    main()
