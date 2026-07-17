#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015-2025 University of Oslo, Norway
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
Removes old entries in the password history tables.

This script removes password history entries that are older than a given
threshold.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import argparse
import datetime
import logging
import textwrap

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.database.ctx import db_context
from Cerebrum.modules.pwcheck.history import PasswordHistory
from Cerebrum.utils.argutils import add_commit_args


logger = logging.getLogger(__name__)


def get_relative_date(years=0, months=0, days=0):
    """
    Calculates relative past date from current time based on input params.

    If no params given, returns todays date.

    :param int years: Number of years from current time (365 days)
    :param int months: Number of months from current time (30 days)
    :param int days: Number of days from current time

    :rtype: datetime.date
    """
    days = days + months * 30 + years * 365
    delta = datetime.timedelta(days=days)
    today = datetime.date.today()
    return today - delta


def delete_password_history(db, threshold):
    ph = PasswordHistory(db)
    logger.info("Deleting password_history entries older than %s", threshold)
    deleted = [r['entity_id'] for r in ph.delete_set_before(threshold)]
    logger.info("Deleted %d password history records for %d accounts",
                len(deleted), len(set(deleted)))


def main(argv=None):
    """ Script invocation. """
    parser = argparse.ArgumentParser(description=__doc__)

    delta_group = parser.add_argument_group(
        "Threshold",
        textwrap.dedent(
            """
            Set the password history date threshold by substracting a
            combination of years, months, and days from the current date.
            """
        ).strip(),
    )
    delta_group.add_argument(
        '-y', '--years',
        dest='years',
        default=0,
        type=int,
        help="Number of years to add to the timedelta",
    )
    delta_group.add_argument(
        '-m', '--months',
        dest='months',
        default=0,
        type=int,
        help="Number of months to add to the timedelta",
    )
    delta_group.add_argument(
        '-d', '--days',
        dest='days',
        default=0,
        type=int,
        help="Number of days to add to the timedelta",
    )
    add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(argv)
    Cerebrum.logutils.autoconf("cronjob", args)
    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    dryrun = not args.commit
    threshold = get_relative_date(
        years=args.years,
        months=args.months,
        days=args.days,
    )

    with db_context(Factory.get('Database')(), dryrun) as db:
        delete_password_history(db, threshold)

    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
