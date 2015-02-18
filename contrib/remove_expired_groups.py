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
This script is used to remove groups that have reached
a defined number of days past expiration-date
"""

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from mx.DateTime import now

logger = Factory.get_logger('cronjob')


def remove_group(db, group, entity_id):
    """
    """
    pass


def remove_expired_groups(db, days, pretend):
    """
    Removes groups that have reached number of `days' past expiration-date.

    :param Cerebrum.Database db: The database connection
    :param int days: Amount of days after past expiration-date
    :param bool pretend: If True, do not actually remove from DB
    """
    try:
        gr = Factory.get('Group')(db)
        expired_groups = gr.search(filter_expired=False, expired_only=True)
        for group in expired_groups:
            if group['expire_date'] + days >= now():
                logger.info('Expired group %s, will now be removed' % (group))
                if not pretend:
                    # TODO
                    pass
            else:
                time_until_removal = group['expire_date'] + days - now()
                logger.debug(
                    'Expired group %s, will be removed in %d days' % (
                        group,
                        int(time_until_removal.days)
                    )
                )
    except Exception:
        logger.error('Unexpected exception', exc_info=1)
        db.rollback()
        raise


def main(args=None):
    """
    """
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-d', '--days',
        dest='days',
        type=int,
        default=30,
        metavar='<days>',
        help='Amount of days to wait after expiration date before '
        'removing the group (default: 30'
    )
    parser.add_argument(
        '-p', '--pretend',
        action='store_true',
        dest='pretend',
        default=False,
        help='Do not actually remove the groups '
        '(default: All matching groups will be removed)'
    )
    logger.info('START %s', parser.prog)
    args = parser.parse_args(args)
    db = Factory.get('Database')()
    db.cl_init(change_program='remove_expired_groups.py')
    remove_expired_groups(db, args.days, args.pretend)
    logger.info('DONE %s', parser.prog)


if __name__ == '__main__':
    main()
