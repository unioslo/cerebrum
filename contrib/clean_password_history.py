#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2015 University of Oslo, Norway
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
Removes entries in the password history database table that are older than
the timedelta specified by using the script's command-line arguments, counting
back from the current time and date.
Multiple arguments may be used at the same time, to get the wanted timedelta.
"""

import argparse
from datetime import datetime, timedelta
from Cerebrum.Utils import Factory
from Cerebrum.modules.pwcheck.history import PasswordHistory


logger = Factory.get_logger('cronjob')


def get_relative_date(years=0, months=0, days=0):
    """
    Calculates relative past date from current time based on input params.
    If no params given, returns todays date.
    :param years: Number of years from current time (365 days)
    :type: int
    :param months: Number of months from current time (30 days)
    :type: int
    :param days: Number of days from current time
    :type: int
    :return: datetime.datetime object
    """

    days = days + months * 30 + years * 365
    delta = timedelta(days=days)
    now  = datetime.today()

    return now - delta


def main():
    """ Script invocation. """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-y', '--years',
        dest='years',
        default=0,
        type=int,
        help='Number of years to add to the timedelta')
    parser.add_argument(
        '-m', '--months',
        dest='months',
        default=0,
        type=int,
        help='Number of months to add to the timedelta')
    parser.add_argument(
        '-d', '--days',
        dest='days',
        default=0,
        type=int,
        help='Number of days to add to the timedelta')
    parser.add_argument(
        '--commit',
        action='store_true',
        default=False,
        help='Commit changes to DB')
    args = parser.parse_args()

    exp_date = get_relative_date(years=args.years,
                                 months=args.months,
                                 days=args.days)

    logger.info(
        'Deleting all entries in password_history before: %s' % exp_date)

    ph = PasswordHistory(Factory.get('Database')())
    ph.del_exp_history(exp_date)
    if args.commit:
        logger.info('Committing changes')
        ph.commit()
    else:
        logger.info('Rolling back changes')
        ph.rollback()
    logger.info('Done')


if __name__ == '__main__':
        main()
