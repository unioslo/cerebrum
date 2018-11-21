#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2015-2018 University of Oslo, Norway
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

from __future__ import unicode_literals

from six import text_type

import cerebrum_path

from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.Utils import Factory
from Cerebrum.database import DatabaseError
from Cerebrum.database import IntegrityError
from mx.DateTime import now

logger = Factory.get_logger('cronjob')
del cerebrum_path


def remove_expired_groups(db, days, pretend):
    """
    Removes groups that have reached number of `days' past expiration-date.

    :param Cerebrum.database.Database db: The database connection
    :param int days: Amount of days after past expiration-date
    :param bool pretend: If True, do not actually remove from DB
    """
    try:
        amount_to_be_removed_groups = 0
        amount_removed_groups = 0
        if pretend:
            logger.info('DRYRUN: Rolling back all changes')
        gr = Factory.get('Group')(db)
        ba = BofhdAuth(db)
        expired_groups = gr.search(filter_expired=False, expired_only=True)
        for group in expired_groups:
            removal_deadline = group['expire_date'] + days
            if now() > removal_deadline:  # deadline passed. remove!
                amount_to_be_removed_groups += 1
                try:
                    gr.clear()
                    gr.find(group['group_id'])
                    exts = gr.get_extensions()
                    if exts:
                        logger.debug("Skipping group %r, has extensions %r",
                                     gr.group_name, exts)
                        continue
                    if ba.list_alterable_entities(gr.entity_id, 'group'):
                        logger.debug("Skipping group %r, is moderator of a "
                                     "group", gr.group_name)
                        continue
                    gr.delete()
                    if not pretend:
                        db.commit()
                    else:  # do not actually remove when running with -d
                        db.rollback()
                    amount_removed_groups += 1
                    logger.info(
                        'Expired group (%s - %s) removed' % (
                            group['name'],
                            group['description']))
                except IntegrityError as e:
                    logger.error('Integrity Error: %r', text_type(e))
                    db.rollback()
                    continue

                except DatabaseError as e:
                    logger.error(
                        'Database error: Could not delete expired group '
                        '(%s - %s): %s. Skipping' % (
                            group['name'],
                            group['description'],
                            text_type(e)),
                        exc_info=True)
                    db.rollback()
                    continue
            else:
                time_until_removal = removal_deadline - now()
                logger.debug(
                    'Expired group (%s - %s), will be removed in %d days' % (
                        group['name'],
                        group['description'],
                        int(time_until_removal.days)))
    except Exception as e:
        logger.critical('Unexpected exception: %s' % (text_type(e)),
                        exc_info=True)
        db.rollback()
        raise
    finally:
        logger.info(
            '%d expired groups, %d selected for removal, '
            '%d actually removed' % (
                len(expired_groups),
                amount_to_be_removed_groups,
                amount_removed_groups))


def main(args=None):
    """
    """
    try:
        import argparse
    except ImportError:
        from Cerebrum.extlib import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--days',
        dest='days',
        type=int,
        default=30,
        metavar='<days>',
        help='Amount of days to wait after expiration date before '
        'removing the group (default: 30'
    )
    parser.add_argument(
        '-p', '--pretend', '-d', '--dryrun',
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
