#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2012-2018 University of Oslo, Norway
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

"""This script produces a dump of names and external ID's from a source system.
The dump is colon-separated data with the external ID and name of the person
tied to the ID. Each line ends with the date and time for when the file was
generated, as required by Datavarehus.

Eg. To dump all employee-numbers from SAP:
    <scipt name> -s SAP -t NO_SAPNO

will produce a file:
    9831;Ola Normann;15/04/2013 09:01:43
    7321;Kari Normann;15/04/2013 09:01:44
    <employee_no>;<employee_name>;<date_time>
    ...

"""
from __future__ import unicode_literals

import sys
import argparse
import time

from six import text_type

from Cerebrum.Utils import Factory
from Cerebrum.utils.atomicfile import AtomicFileWriter


logger = Factory.get_logger('cronjob')
db = Factory.get('Database')()
pe = Factory.get('Person')(db)
co = Factory.get('Constants')(db)


def get_external_ids(source_system, id_type):
    """Fetches a list of people, their external ID and their name from a source
    system.

    :param AuthoritativeSystem source_sys:
        The authorative system to list from.

    :param EntityExternalId id_type:
        The external ID type to list.

    :rtype: list
    :returns: A list of dictionary objects with the keys:
               'entity_id' -> <int> Entity id of the person
               'ext_id'    -> <string> External id
               'name'      -> <string> Full name of the employee
    """
    ext_ids = []
    persons = pe.list_external_ids(source_system=source_system,
                                   id_type=id_type,
                                   entity_type=co.entity_person)
    names = pe.getdict_persons_names(source_system=co.system_cached,
                                     name_types=co.name_full)
    for person in persons:
        try:
            name = names[person['entity_id']][int(co.name_full)]
        except KeyError:
            logger.warn("No name for person with external id '%d'. \
                         Excluded from list.", person['entity_id'])
            continue
        entry = {
            'entity_id': person['entity_id'],
            'ext_id': person['external_id'],
            'name': name
        }
        ext_ids.append(entry)
    return sorted(ext_ids, key=lambda x: x['ext_id'])


def main():
    parser = argparse.ArgumentParser(
        description=('Generate a semicolon-separated file with employee IDs '
                     'and employee names.'))
    parser.add_argument(
        '-o', '--output',
        type=text_type,
        help='output file (default: stdout)')
    parser.add_argument(
        '-s', '--source-system',
        type=lambda x: co.human2constant(x, co.AuthoritativeSystem),
        help='code for source system')
    parser.add_argument(
        '-t', '--id-type',
        type=lambda x: co.human2constant(x, co.EntityExternalId),
        help='code for external ID type')
    args = parser.parse_args()

    if not args.source_system:
        parser.error("No valid source system provided")
    if not args.id_type:
        parser.error("No valid external ID type provided")

    # Generate selected report
    logger.info("Started dump to %s", args.output)
    external_ids = get_external_ids(args.source_system, args.id_type)
    if not external_ids:
        logger.error('Found nothing to write to file')
        sys.exit(1)
    with AtomicFileWriter(args.output, encoding='latin1') as f:
        for id_name in external_ids:
            f.write("%s\n" % ';'.join(
                (id_name['ext_id'],
                 id_name['name'],
                 time.strftime('%m/%d/%Y %H:%M:%S'))))
    logger.info("Done")


if __name__ == "__main__":
    main()
