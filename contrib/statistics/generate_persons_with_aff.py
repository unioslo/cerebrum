#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2018 University of Oslo, Norway""
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

"""
This script lists all persons with a specific affiliation and an active
primary account.
"""

from __future__ import unicode_literals

import argparse
import os
import sys
import jinja2
import datetime
from six import text_type

from Cerebrum.Utils import Factory
from Cerebrum.utils.funcwrap import memoize

logger = Factory.get_logger("cronjob")
db = Factory.get(b'Database')()
pe = Factory.get(b'Person')(db)
ac = Factory.get(b'Account')(db)
co = Factory.get(b'Constants')(db)
ou = Factory.get(b'OU')(db)

pe2sapid = dict((r['entity_id'], r['external_id']) for r in
           pe.list_external_ids(source_system=co.system_sap,
           id_type=co.externalid_sap_ansattnr))

@memoize
def ou_info(ou_id):
    ou.clear()
    ou.find(ou_id)
    sko = "{:02d}{:02d}{:02d}".format(ou.fakultet, ou.institutt, ou.avdeling)
    name = ou.get_name_with_language(name_variant=co.ou_name_acronym,
                                     name_language=co.language_nb)
    return sko, name


def persons_with_aff_status(status):
    data = []
    for row in pe.list_affiliations(status=status):
        person_id = row['person_id']
        sap_id = pe2sapid.get(person_id)
        ou_id = row['ou_id']
        pe.clear()
        pe.find(person_id)
        primary = pe.get_primary_account()
        if not primary:
            continue
        ac.clear()
        ac.find(primary)
        if ac.is_expired():
            continue
        full_name = pe.get_name(source_system=co.system_cached,
                                variant=co.name_full)
        birth = pe.birth_date.Format('%Y-%m-%d')
        sko, ou_name = ou_info(ou_id)
        if not isinstance(full_name, text_type):
            full_name = full_name.decode('latin1')
        if not isinstance(ou_name, text_type):
            ou_name = ou_name.decode('latin1')
        data.append({
            'account_name': ac.account_name,
            'person_name': full_name,
            'birth': birth,
            'sap_id': sap_id,
            'affiliation': text_type(status),
            'ou_sko': sko,
            'ou_name': ou_name,
        })
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--aff-status',
        type=co.human2constant,
        dest='status',
        required=True,
        help='Lists persons with this affiliation status')
    parser.add_argument(
        '-o', '--output',
        type=str,
        dest='output',
        default='',
        help='The file to print the report to. Defaults to stdout.')
    args = parser.parse_args()

    logger.info('Starting with args: {}'.format(args))

    persons = persons_with_aff_status(args.status)
    sorted_persons = sorted(persons,
                            key=lambda x: (x['ou_sko'],
                                           x['account_name']))
    logger.info('Found {} affiliations'.format(len(persons)))
    logger.info('Found {} unique persons'.format(
                len(set(map(lambda x: x['account_name'], persons)))))

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__),
                                       'templates')))
    template = env.get_template('simple_list_overview.html')
    iso_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    title = 'List of persons with affiliation {aff} ({timestamp})'.format(
        timestamp=iso_timestamp, aff=args.status)
    output_str = template.render(
        headers=(
            ('account_name', 'Account name'),
            ('person_name', 'Name'),
            ('birth', 'Birth date'),
            ('sap_id', "SAP Id"),
            # ('affiliation', 'Affiliation'),
            ('ou_sko', 'OU'),
            ('ou_name', 'OU acronym')),
        title=title,
        prelist='<h3>{}</h3>'.format(title),
        items=sorted_persons).encode('utf-8')
    if args.output:
        with open(args.output, 'w') as fp:
            fp.write(output_str)
    else:
        sys.stdout.write(output_str)
    logger.info('Done')


if __name__ == "__main__":
    main()
