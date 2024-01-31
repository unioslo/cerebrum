#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2013-2023 University of Oslo, Norway
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
Count active accounts to be used for invoicing by UiO.

University of Oslo hosts Cerebrum for various partners. The invoice is based on
the number of «active accounts» in the Cerebrum instance.

The returned number is only for what is *right now*. No history is supported.
To get data from previous dates, you need either to log the output, or get a
copy from the database from that date.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import argparse
import csv
import datetime
import logging

import six

import Cerebrum.logutils
import cereconf
from Cerebrum.utils.email import sendmail
from Cerebrum.utils import argutils
from Cerebrum.utils import date_compat

from Cerebrum import Errors
from Cerebrum.Utils import Factory

logger = logging.getLogger(__name__)

MAIL_FROM = 'cerebrum@ulrik.uio.no'
MAIL_SUBJECT = 'Cerebrum invoice report'

AFFILIATIONS = ('STUDENT', 'ANSATT', 'TILKNYTTET',
                'ELEV', 'MANUELL', 'PROJECT')


def get_last_event(db):
    """ Get last logged event. """
    last_event = None
    # TODO: Replace changelog with audit log?
    try:
        last_event = db.query_1(
            """
              SELECT MAX(tstamp)
              FROM [:table schema=cerebrum name=change_log]
            """
        )
    except Errors.NotFoundError:
        pass
    last_event = date_compat.get_datetime_tz(last_event)
    logger.debug("Last event found from db: %s", last_event)
    return last_event


def get_affiliated(db):
    """ Get all affiliated person ids. """
    pe = Factory.get('Person')(db)
    co = pe.const

    affiliations = []
    for aff_string in AFFILIATIONS:
        try:
            affiliations.append(
                co.get_constant(co.PersonAffiliation, aff_string))
        except LookupError:
            pass
    logger.debug("Active affiliations: %s",
                 ', '.join(six.text_type(a) for a in affiliations))

    persons = set(r['person_id']
                  for r in pe.list_affiliations(affiliation=affiliations,
                                                include_deleted=False))
    logger.debug("Found %d persons with active aff", len(persons))
    return persons


def get_quarantined_accounts(db):
    """ Get all quarantined account ids. """
    ac = Factory.get('Account')(db)
    co = ac.const

    quars = set(r['entity_id']
                for r in ac.list_entity_quarantines(
                    only_active=True,
                    entity_types=co.entity_account,
                ))
    logger.debug("Found %d quarantined accounts", len(quars))
    return quars


def process(output, mail):
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)

    logger.debug("Using database: %s", cereconf.CEREBRUM_DATABASE_NAME)

    last_event = get_last_event(db)

    # Find active persons
    all_affiliated = get_affiliated(db)

    # Find inactive accounts
    quars = get_quarantined_accounts(db)

    active_accounts = set(
        r['account_id']
        for r in ac.search(owner_type=co.entity_person)
        if (r['owner_id'] in all_affiliated
            and r['account_id'] not in quars))
    logger.info("Found %d accounts for the active persons",
                len(active_accounts))

    last_event_str = date_compat.to_mx_format(last_event) if last_event else ""
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    num_accounts = len(active_accounts)

    if output:
        # TODO: We may want to use Cerebrum.utils.csvutils for unicode support
        csvw = csv.writer(output)
        csvw.writerow((
            today_str,
            cereconf.CEREBRUM_DATABASE_NAME,
            num_accounts,
            last_event_str,
        ))
        logger.info("wrote report to: %s", output)

    if mail:
        body = "Found {num} active accounts in {db} from {when}".format(
            num=num_accounts,
            db=cereconf.CEREBRUM_DATABASE_NAME,
            when=last_event_str,
        )
        sendmail(mail, MAIL_FROM, MAIL_SUBJECT, body)
        logger.info("sent report to: %s", mail)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-o', '--output-file',
        dest='output',
        type=argparse.FileType('a'),
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
    logger.info("start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    with argutils.ParserContext(parser):
        if not any((args.output, args.mail)):
            raise ValueError("no action provided")

    process(args.output, args.mail)
    logger.info("done %s", parser.prog)


if __name__ == '__main__':
    main()
