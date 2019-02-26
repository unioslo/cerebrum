#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2013, 2017, 2018, 2019 University of Oslo, Norway
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
""" Count active accounts to be used for invoicing by UiO.

University of Oslo hosts Cerebrum for various partners. The invoice is based on
the number of «active accounts» in the Cerebrum instance.

The returned number is only for what is *right now*. No history is supported.
To get data from previous dates, you need either to log the output, or get a
copy from the database from that date.

"""

from __future__ import unicode_literals

import argparse
import csv
import logging
import time
from six import text_type

import Cerebrum.logutils
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory

logger = logging.getLogger(__name__)


def process(output, mail):
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    pe = Factory.get('Person')(db)

    logger.info("Invoice stats started")
    logger.debug("Using database: %s", cereconf.CEREBRUM_DATABASE_NAME)
    last_event = None
    try:
        last_event = db.query_1('''
            SELECT tstamp FROM [:table schema=cerebrum name=change_log]
            ORDER BY tstamp DESC
            LIMIT 1''')
    except Errors.NotFoundError:
        pass
    logger.debug("Last event found from db: %s", last_event)

    # Find active persons:
    affs = []
    for a in ('STUDENT', 'ANSATT', 'TILKNYTTET', 'ELEV', 'MANUELL', 'PROJECT'):
        try:
            af = co.PersonAffiliation(a)
            int(af)
            affs.append(af)
        except Errors.NotFoundError:
            pass
    logger.debug("Active affiliations: %s" % ', '.join(text_type(a) for a in
                                                       affs))
    all_affiliated = set(r['person_id'] for r in pe.list_affiliations(
                                affiliation=affs,
                                include_deleted=False))
    logger.debug("Found %d persons with active aff", len(all_affiliated))

    # Find active accounts:
    quars = set(r['entity_id'] for r in
                ac.list_entity_quarantines(only_active=True,
                                           entity_types=co.entity_account))
    logger.debug("Found %d quarantined accounts", len(quars))

    active_accounts = set(r['account_id'] for r in
                          ac.search(owner_type=co.entity_person) if
                          (r['owner_id'] in all_affiliated and r['account_id']
                           not in quars))
    logger.info("Found %d accounts for the active persons",
                len(active_accounts))

    if output:
        csvw = csv.writer(output)
        csvw.writerow((time.strftime('%Y-%m-%d'),
                       cereconf.CEREBRUM_DATABASE_NAME,
                       len(active_accounts),
                       last_event,
                       ))

    logger.info("Invoice stats finished")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-o', '--output-file',
        dest='output', type=argparse.FileType('a'),
        help='Append invoice data, in CSV format'
    )
    parser.add_argument(
        '-m', '--mail',
        dest='mail',
        help='Send invoice report to given mail address'
    )

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()
    Cerebrum.logutils.autoconf('cronjob', args)

    process(args.output, args.mail)


if __name__ == '__main__':
    main()
