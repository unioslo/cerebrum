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
from mx import DateTime

from Cerebrum.Utils import Factory
from Cerebrum.modules.pwcheck.history import PasswordHistory


logger = Factory.get_logger('cronjob')


def get_relative_date(years=None, months=None, days=None):
    """
    Calculates relative past date from current time based on input params.
    :param years: Number of years from current time
    :type: str
    :param months: Number of months from current time
    :type: str
    :param days: Number of days from current time
    :type: str
    :return: mx.DateTime.DateTime object
    """
    exp_date = DateTime.now()
    if years is not None:
        exp_date = exp_date - DateTime.RelativeDate(years=int(years))
    if months is not None:
        exp_date = exp_date - DateTime.RelativeDate(months=int(months))
    if days is not None:
        exp_date = exp_date - DateTime.RelativeDate(days=int(days))
    return exp_date


def main():
    """ Script invocation. """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-y', '--years',
        dest='years',
        help='Number of years to add to the timedelta')
    parser.add_argument(
        '-m', '--months',
        dest='months',
        help='Number of months to add to the timedelta')
    parser.add_argument(
        '-d', '--days',
        dest='days',
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
