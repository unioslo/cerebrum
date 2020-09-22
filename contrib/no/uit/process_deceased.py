#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2009-2019 University of Tromsø, Norway
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
Read and import employee deceased dates.

Imports deceased dates from a CSV file.
"""
import argparse
import csv
import datetime
import logging

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import add_commit_args

logger = logging.getLogger(__name__)

default_charsep = ';'
default_encoding = 'utf-8'

KEY_PAGANR = "paganr"
KEY_FNR = "ssn"
KEY_LNAME = "lname"
KEY_FNAME = "fname"
KEY_DATE = "date"
KEY_REASON = "reason"


def parse_date(date_str, date_fmt='%d.%m.%Y'):
    """
    Parses a date from a string using date_fmt as format.
    Default format dd.mm.yyyy e.g. '01.05.1985'  (1st May 1985)
    Note: dot as separator.
    Return datetime.Date with the specified date.
    """
    parsed = datetime.datetime.strptime(date_str, date_fmt)
    return parsed.date()


def get_deceased(db):
    person = Factory.get('Person')(db)
    deceased_ids = list()
    for row in person.list_deceased():
        deceased_ids.append(row['person_id'])
    return deceased_ids


def read_csv_file(filename,
                  encoding=default_encoding,
                  charsep=default_charsep):
    """
    Read CSV file with a header line.
    """
    logger.info("reading csv file=%r (encoding=%r, charsep=%r)",
                filename, encoding, charsep)
    count = 0
    with open(filename, mode='r') as f:
        for data in csv.DictReader(f, delimiter=charsep.encode(encoding)):
            yield {k.decode(encoding): v.decode(encoding)
                   for k, v in data.items()}
            count += 1
    logger.info("read %d entries from file=%r", count, filename)


def build_deceased_cache(csv_data):
    """
    Transform CSV data into a employee_id lookup map.

    Builds a dict that maps from employee_id -> relevant person data for
    :py:func:`process_deceased`.
    """
    persons = dict()
    for detail in csv_data:
        if detail[KEY_PAGANR] in persons:
            logger.warning("Duplicate entry for %r", detail[KEY_PAGANR])
        persons[detail[KEY_PAGANR]] = {
            'fnr': detail[KEY_FNR],
            'lname': detail[KEY_LNAME],
            'fname': detail[KEY_FNAME],
            'deceased_date': parse_date(detail[KEY_DATE]),
            'reason': detail[KEY_REASON]
        }
    return persons


def process_deceased(db, source_data):
    person = Factory.get('Person')(db)
    co = Factory.get('Constants')(db)

    for key, item in source_data.items():
        person.clear()
        try:
            person.find_by_external_id(co.externalid_paga_ansattnr, key)
        except Errors.NotFoundError:
            logger.error("Person with employee_id=%r not found", key)
            continue
        else:
            logger.debug("Processing person with employee_id=%r, date=%r",
                         key, item['deceased_date'])

        deceased_date = item['deceased_date']

        if person.deceased_date == deceased_date:
            logger.debug("No change in deceased_date for employee_id=%r", key)
            continue

        if person.deceased_date:
            logger.info("Setting deceased date for employee_id=%r to date=%r",
                        key, deceased_date)
        else:
            logger.warning("Updating deceased date for employee_id=%r "
                           "to date=%r (was=%r)",
                           key, deceased_date, person.deceased_date)

        person.deceased_date = deceased_date
        person.description = "Deceased, set by {chprog} on {dt}".format(
            chprog=db.change_program,
            dt=datetime.datetime.now().isoformat())
        person.write_db()


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Import deceased dates from Paga",
    )
    parser.add_argument(
        '-f', '--file',
        dest='filename',
        # default=default_person_file,
        help='Read and import deceased dates from %(metavar)s',
        metavar='csv-file',
    )
    add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)
    logger.info('Start of %s', parser.prog)
    logger.debug('args: %r', args)
    db = Factory.get('Database')()
    db.cl_init(change_program=parser.prog)

    source = build_deceased_cache(read_csv_file(args.filename))
    process_deceased(db, source)

    if args.commit:
        logger.info('Commiting changes')
        db.commit()
    else:
        logger.info('Rolling back changes')
        db.rollback()


if __name__ == '__main__':
    main()
