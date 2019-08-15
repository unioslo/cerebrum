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

"""
Figures out which employees should be exported to CIM based on SAP
employment data."""

import argparse

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.xmlutils.sapxml2object import SAPXMLDataGetter

logger = Factory.get_logger('cronjob')
db = Factory.get('Database')()
db.cl_init(change_program='update_cim_spreads')
co = Factory.get('Constants')(db)
pe = Factory.get('Person')(db)


def is_eligible(person):
    return filter(lambda x: (x.is_active() and
                             x.kind in (x.HOVEDSTILLING, x.BISTILLING) and
                             x.mg not in (8, 9) and
                             x.mug not in (4, 5, 22, 50)),
                  person.iteremployment())


def get_eligible(parser, include=[]):
    eligible = set()
    for person in parser.iter_person():
        try:
            pe.clear()
            pe.find_by_external_id(source_system=co.system_sap,
                                   id_type=co.externalid_sap_ansattnr,
                                   entity_type=co.entity_person,
                                   external_id=person.get_id(person.SAP_NR))
        except Errors.NotFoundError:
            continue

        if is_eligible(person) or pe.entity_id in include:
            eligible.add(pe.entity_id)
    return eligible


def update_spreads(eligible, spread):
    current = set([x['person_id'] for x in pe.search(spread=spread)])
    to_add = eligible - current
    to_remove = current - eligible

    for person_id in to_add:
        logger.info('Adding person_id:%s', person_id)
        pe.clear()
        pe.find(person_id)
        pe.add_spread(spread)
        pe.write_db()

    for person_id in to_remove:
        logger.info('Removing person_id:%s', person_id)
        pe.clear()
        pe.find(person_id)
        pe.delete_spread(spread)
        pe.write_db()

    return to_add, to_remove


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    required = parser.add_argument_group('required arguments')
    required.add_argument('-f', '--sap-file',
                          dest='sap_file',
                          required=True,
                          help='XML file containing person and employment '
                               'data from SAP.')
    required.add_argument('-s', '--spread',
                          dest='spread',
                          required=True,
                          help='spread to add or remove for eligible persons')
    parser.add_argument('-i', '--include',
                        dest='include',
                        action='append',
                        default=[],
                        help='always consider this person (ID) to be eligible')
    parser.add_argument('-c', '--commit',
                        dest='commit',
                        action='store_true',
                        help='should changes be committed?')
    args = parser.parse_args()

    spread = co.Spread(args.spread)
    int(spread)

    if args.commit:
        logger.info('Running in commit mode')
    else:
        logger.info('Running in dryrun mode')

    logger.info('Parsing SAP file and figuring out eligibility ...')
    parser = SAPXMLDataGetter(filename=args.sap_file,
                              logger=logger,
                              fetchall=False)
    eligible = get_eligible(parser, map(int, args.include))
    logger.info('Done parsing SAP file')

    logger.info('Updating spreads...')
    added, removed = update_spreads(eligible, spread)
    logger.info('Added %s persons', len(added))
    logger.info('Removed %s persons', len(removed))
    logger.info('Total with spread %s: %s',
                str(spread),
                len(set([x['person_id'] for x in pe.search(spread=spread)])))

    if args.commit:
        logger.info('Committing changes...')
        db.commit()
    else:
        logger.info('Rolling back changes...')
        db.rollback()

if __name__ == "__main__":
    main()
