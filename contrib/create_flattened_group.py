#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2020 University of Oslo, Norway
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
This script extracts all direct and indirect members of a group and produces a
flattened version thereof.
"""
import logging
import cereconf

from Cerebrum import Errors
from Cerebrum import logutils
from Cerebrum.Account import Account
from Cerebrum.Utils import Factory
from Cerebrum.utils import argutils

logger = logging.getLogger(__name__)
 

def prepare_empty(db, args):
    """This function constructs a destination group
    if it doesn't exist."""
    co = Factory.get('Constants')(db)
    gr = Factory.get('Group')(db)
    try:
        gr.find_by_name(args.destination_group)
    except Errors.NotFoundError:
        bootstrap_ac = Account(db)
        bootstrap_ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        gr.populate(
            creator_id=bootstrap_ac.entity_id,
            visibility=co.group_visibility_all,
            name=args.destination_group,
            description=('Flattened variant of %s' % args.target_group),
            group_type=co.group_type_internal,
        )
    gr.write_db()


def update_flattened_derivative(db, flattened, flattened_groupname):
    """This function updates the memberships in the destination group."""
    co = Factory.get('Constants')(db)
    gr = Factory.get('Group')(db)
    gr.find_by_name(flattened_groupname)
    present_ids = set(member['member_id'] for member in gr.search_members(
        group_id=gr.entity_id, member_type=co.entity_account))
    future_ids = set(member['member_id'] for member in flattened)
    # Rather than chucking everyone out and adding all (new) members back in,
    # we just update the (possibly pre-existing) list in order to minimize
    # redundant change_log abuse.
    for member in future_ids - present_ids:
        gr.add_member(member)
    for member in present_ids - future_ids:
        gr.remove_member(member)
    gr.write_db()


def main(inargs=None):
    """
    Find all direct and indirect members of a group and create a new and
    flatter version.
    """
    try:
        import argparse
    except ImportError:
        from Cerebrum.extlib import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-t', '--target-group',
        dest='target_group',
        required=True,
        default=None,
        help='Group to be flattened'
    )
    parser.add_argument(
        '-d', '--destination-group',
        dest='destination_group',
        required=True,
        default=None,
        help='Flattened group'
    )
    logutils.options.install_subparser(parser)

    argutils.add_commit_args(parser, default=False)
    args = parser.parse_args(inargs)
    logutils.autoconf('cronjob', args)

    logger.info('START %s', parser.prog)
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    gr = Factory.get('Group')(db)
    try:
        gr.find_by_name(args.target_group)
    except Errors.NotFoundError:
        parser.error(
            'Target group {} does not exist.'.format(args.target_group))
    logger.info('Searching group %s for direct and indirect members')
    flattened = gr.search_members(group_id=gr.entity_id,
                                  indirect_members=True,
                                  member_type=co.entity_account)
    logger.info('Preparing flattened group %s', args.destination_group)
    prepare_empty(db, args)
    logger.info('Updating: Group %s to contain %i members',
                args.destination_group, len(flattened))
    update_flattened_derivative(db, flattened, args.destination_group)

    if args.commit:
        logger.info("Committing changes")
        db.commit()
    else:
        db.rollback()
        logger.info("Changes rolled back (dryrun)")

    logger.info('DONE %s', parser.prog)


if __name__ == '__main__':
    main()
