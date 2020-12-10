#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002-2019 University of Oslo, Norway
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
This script loads list of SKO/YRK (STYRK) from csv file
(which is converted excel sheet)

Specifically, csv input file with information about SKO and YRK relation if
there is any and commits them to the DB
"""
from __future__ import print_function, unicode_literals

import argparse
import csv
import logging

from Cerebrum.Utils import Factory
from Cerebrum.modules.no.orgera import job_codes

logger = logging.getLogger(__name__)

db = Factory.get('Database')()


def parse_csv(infile, delimiter):

    with open(infile, 'r') as csvfile:
        csv_reader = csv.reader(csvfile, delimiter=str(delimiter))
        csv_reader.next()  # Skip header

        stilling = "Stillingen mangler beskrivelse"
        yrkeskodebetegnelse = "Yrkeskode mangler beskrivelse"
        for row in csv_reader:
            sko = row[0]
            styrk = row[2]

            try:
                stilling = row[1].decode('utf-8')
            except Exception as e:
                logger.error(e)

            try:
                yrkeskodebetegnelse = row[3].decode('utf-8')
            except Exception as e:
                logger.error(e)

            if not sko or not styrk:
                continue

            job_codes.assert_sko(db, sko, stilling)
            job_codes.assert_styrk(db, styrk, yrkeskodebetegnelse)


def main(inargs=None):
    doc = __doc__.strip().splitlines()

    parser = argparse.ArgumentParser(
        description=doc[0],
        epilog='\n'.join(doc[3:]),
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument(
        '--commit',
        action='store_true',
        default=False,
        help="Actually commit this to the database"
    )

    parser.add_argument(
        '--delimiter',
        default=",",
        help="Actually commit this to the database"
    )

    parser.add_argument(
        'file',
        help="input file"
    )

    args = parser.parse_args(inargs)

    logger.info('Start of script %s', parser.prog)

    parse_csv(args.file, args.delimiter)

    if not args.commit:
        db.rollback()
        logger.info("Rolled back all changes")
    else:
        db.commit()
        logger.info("Committed all changes")


if __name__ == '__main__':
    main()
