#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2013, 2017, 2018 University of Oslo, Norway
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
""" Count active accounts to be used for invoicing by USIT

USIT, at the University of Oslo, is hosting Cerebrum for various partners. The
invoice is based on the number of «active accounts» in the Cerebrum instance.

The returned number is only for what is *right now*. No history is supported.
To get data from previous dates, you need either to log the output, or get a
copy from the database from that date. It is possible to fetch some number for
previous dates, but there be dragons (missing/outdated data etc).

"""

import argparse
import time

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory

logger = Factory.get_logger('console')


def process():
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    pe = Factory.get('Person')(db)

    logger.info("Invoice stats started")
    logger.info("Using database: %s", cereconf.CEREBRUM_DATABASE_NAME)
    last_event = None
    try:
        last_event = db.query_1('''
            SELECT tstamp FROM [:table schema=cerebrum name=change_log]
            ORDER BY tstamp DESC
            LIMIT 1''')
    except Errors.NotFoundError:
        pass
    logger.info("Last event found from db: %s" % last_event)

    # Find active persons:
    affs = []
    for a in ('STUDENT', 'ANSATT', 'TILKNYTTET', 'ELEV', 'MANUELL', 'PROJECT'):
        try:
            af = co.PersonAffiliation(a)
            int(af)
            affs.append(af)
        except Errors.NotFoundError:
            pass
    logger.info("Active affiliations: %s" % ', '.join(str(a) for a in affs))

    all_affiliated = set(r['person_id'] for r in pe.list_affiliations(
                                affiliation=affs,
                                include_deleted=False))
    logger.info("Found %d persons with active aff", len(all_affiliated))

    # Find active accounts:
    quars = set(r['entity_id'] for r in
                ac.list_entity_quarantines(only_active=True,
                                           entity_types=co.entity_account))
    logger.info("Found %d quarantined accounts", len(quars))

    active_accounts = set(r['account_id'] for r in
                          ac.search(owner_type=co.entity_person) if
                          (r['owner_id'] in all_affiliated and r['account_id']
                           not in quars))
    logger.info("Found %d accounts for the active persons",
                len(active_accounts))

    print
    print("Tidspunkt: {}".format(time.strftime('%Y-%m-%d')))
    print("Database: {} (sist aktivitet: {})".format(
        cereconf.CEREBRUM_DATABASE_NAME, last_event))
    print
    print("Antal aktive brukere: {}".format(len(active_accounts)))
    print
    logger.info("Invoice stats finished")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    process()

if __name__ == '__main__':
    main()
