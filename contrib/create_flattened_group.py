#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2005-2020 University of Oslo, Norway
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
This script extracts all direct and indirect members of a group and producves a
flattened version thereof.
"""

import sys

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.Account import Account


def prepare_empty(db, gr, args):
    """
    This function either empties an existing destination group
    or, failing at that,  constructs a new one."""
    co = Factory.get('Constants')(db)
    gr.clear()
    try:
        gr.find_by_name(args.destination_group)
        for member in gr.search_members(group_id=gr.entity_id):
            gr.remove_member(member['member_id'])
    except Errors.NotFoundError:
        bootstrap_ac = Account(db)
        bootstrap_ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        gr.populate(
            creator_id=bootstrap_ac.entity_id,
            visibility=co.group_visibility_all,
            name=args.destination_group,
            description=('Flattened variant of %s' % args.target_group),
            group_type=co.group_type_manual,
        )
    gr.write_db()


def add_members_to_flattened_derivative(gr, flattened, flattened_groupname):
    """This function adds all members found to the destination group."""
    gr.clear()
    gr.find_by_name(flattened_groupname)
    ids = set(member['member_id'] for member in flattened)
    for member in ids:
        gr.add_member(member)
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
    logger = Factory.get_logger(__name__)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-t', '--target-group',
        dest='target_group',
        default=None,
        help='Group to be flattened'
    )
    parser.add_argument(
        '-d', '--destination-group',
        dest='destination_group',
        default=None,
        help='Flattened group'
    )
    parser.add_argument(
        '-c', '--commit',
        default=False,
        action='store_true',
        help='Commit changes')
    args = parser.parse_args(inargs)
    if not args.target_group or not args.destination_group:
        logger.error('Both target and destination group must be provided')
        sys.exit()
    logger.info('START %s', parser.prog)
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    gr = Factory.get('Group')(db)
    try:
        gr.find_by_name(args.target_group)
    except Errors.NotFoundError:
        logger.error('Target group %s does not exist.', args.target_group)
        sys.exit()
    logger.info('Searching group %s for direct and indirect members')
    flattened = gr.search_members(group_id=gr.entity_id,
                                  indirect_members=True,
                                  member_type=co.entity_account)
    logger.info('Preparing flattened group %s', args.destination_group)
    prepare_empty(db, gr, args)
    logger.info('Adding %i members to %s',
                len(flattened), args.destination_group)
    add_members_to_flattened_derivative(
        gr, flattened, args.destination_group)

    if args.commit:
        logger.info("Committing changes")
        db.commit()
    else:
        db.rollback()
        logger.info("Changes rolled back (dryrun)")

    logger.info('DONE %s', parser.prog)


if __name__ == '__main__':
    main()
