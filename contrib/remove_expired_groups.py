#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2015-2019 University of Oslo, Norway
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


from Cerebrum.Utils import Factory
from Cerebrum.database import DatabaseError
from mx.DateTime import now

logger = Factory.get_logger('cronjob')


def remove_expired_groups(db, days, pretend):
    """
    Removes groups that have reached number of `days' past expiration-date.

    :param Cerebrum.database.Database db: The database connection
    :param int days: Amount of days after past expiration-date
    :param bool pretend: If True, do not actually remove from DB
    """
    # Caching the default file group of users
    logger.info('Caching personal file groups of users')
    pu = Factory.get('PosixUser')(db)
    posix_user2gid = {}
    posix_users = pu.list_posix_users()
    empty_posix_groups = 0
    for row in posix_users:
        posix_user2gid[row['account_id']] = row['gid']
    try:
        amount_to_be_removed_groups = 0
        amount_removed_groups = 0
        if pretend:
            logger.info('DRYRUN: Rolling back all changes')
        gr = Factory.get('Group')(db)
        expired_groups = gr.search(filter_expired=False, expired_only=True)
        for group in expired_groups:
            removal_deadline = group['expire_date'] + days
            if now() > removal_deadline:  # deadline passed. remove!
                amount_to_be_removed_groups += 1
                try:
                    gr.clear()
                    gr.find(group['group_id'])
                    exts = gr.get_extensions()
                    # 1     - If extensions exists, do not delete group.
                    # 1.1   - If the only extension is PosixGroup, then all
                    #         removable members must be removed from group.
                    # 1.1.1 - Group members are removable if, and only if,
                    #         they have some other group as their Default
                    #         File Group (DFG).
                    # 1.1.2 - Corollary: Members with this group as their DFG
                    #         are not removable.
                    # 1.2   - If there are any other extensions than, then the
                    #         group shall be left untouched.
                    # 2     - Groups without any extensions are deleted

                    # 1.1 Only extension as PosixGroup, possible removal
                    if exts and len(exts) == 1 and exts[0] == 'PosixGroup':
                        dfg_members = 0
                        non_dfg_members = 0
                        for row in gr.search_members(group_id=gr.entity_id):
                            member = int(row['member_id'])
                            if member in posix_user2gid:
                                # 1.1.1 - remove member and update counter
                                if posix_user2gid[member] != gr.entity_id:
                                    gr.remove_member(member)
                                    non_dfg_members += 1
                                # 1.1.2 - group member is irremovable
                                else:
                                    dfg_members += 1
                            else:
                                # PosixGroup, but not PosixUser..? This should
                                # never happen, but should be noted if it does.
                                logger.warning('Member %i of PosixGroup %r '
                                               'is not a PosixUser',
                                               member, gr.entity_id)
                        # At least one members has been removed from group
                        if non_dfg_members:
                            logger.debug('Removed %i non-DFG members from '
                                         'PosixGroup %r. %i DGF members '
                                         'remains', non_dfg_members,
                                         gr.entity_id, dfg_members)
                        # There are still members in the group, but no removal
                        elif dfg_members:
                            logger.debug('%i members has PosixGroup %r as'
                                         ' their DFG. No members removed',
                                         dfg_members, gr.entity_id)
                        # PosixGroup was empty all along
                        else:
                            empty_posix_groups += 1
                    # 1.2 Other extensions than PosixGroup - do not touch
                    elif exts:
                        logger.debug('Extensions %r in group %r - skipping!',
                                     exts, gr.entity_id)
                    # 2 No extensions, group is deleted
                    else:
                        gr.delete()
                        amount_removed_groups += 1
                        logger.info(
                            'Expired group (%s - %s) removed' % (
                                group['name'],
                                group['description']))
                    if not pretend:
                        db.commit()
                    else:  # do not actually remove when running with -d
                        db.rollback()
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
        logger.debug('%i empty posixgroups left untouched', empty_posix_groups)
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
