#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2007-2022 University of Oslo, Norway
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
The groups it-uio-ms365-student, it-uio-ms365-ansatt, it-uio-ms365-betalende,
and it-uio-ms365-andre  determine lisences in AzureAD. AzureAD cannot handle
cases where users are members of more than one of these groups at a time.

This script updates memberships in these groups, and ensures orthogonality
between them.
"""

import argparse
import logging

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import add_commit_args

logger = logging.getLogger(__name__)


def sync_group(db, target_group, include_groups=None, exclude_groups=None,
               commit=False):
    """
    Update members of target group, based on membership in other groups.

    :param Cerebrum.database.Database db: A Database object.
    :param str target_group: Target group.
    :param list include_groups: Members from these groups are added to
    target group.
    :param list exclude groups: Members from these groups are not added
    target group, even if members of include_groups.
    :param bool commit: Commit changes to Cerebrum database.
    """
    gr = Factory.get('Group')(db)

    include_group_members = set()
    if include_groups:
        for include_group in include_groups:
            gr.find_by_name(include_group)
            for m in gr.search_members(group_id=gr.entity_id,
                                       indirect_members=True,
                                       member_filter_expired=False):
                include_group_members.add(m['member_id'])
            gr.clear()
        logger.info("Found %s members of %s", len(include_group_members),
                    include_groups)

    exclude_group_members = set()
    if exclude_groups:
        for exclude_group in exclude_groups:
            gr.find_by_name(exclude_group)
            for m in gr.search_members(group_id=gr.entity_id,
                                       member_filter_expired=False):
                exclude_group_members.add(m['member_id'])
            gr.clear()
        logger.info("Found %s members of %s", len(exclude_group_members),
                    exclude_groups)

    gr.find_by_name(target_group)
    current_members = {m['member_id'] for m in gr.search_members(
        group_id=gr.entity_id, member_filter_expired=False)}
    logger.info("%s has %s current members", target_group, len(current_members))

    add_members = include_group_members - exclude_group_members - current_members
    logger.info("Adding %s new members to %s", len(add_members), target_group)
    for member in add_members:
        gr.add_member(member)
        logging.debug('Added new member %r to group %r', member, target_group)

    remove_members = ((current_members - include_group_members)
                      |(current_members.intersection(exclude_group_members)))
    logger.info("Removing %s members from %s", len(remove_members), target_group)
    for member in remove_members:
        gr.remove_member(member)
        logging.debug('Removed member %r from group %r', member, target_group)

    if commit:
        db.commit()
        logger.info("Synced group %s", target_group)
    else:
        db.rollback()
        logger.debug("Dryrun mode, rolling back changes")

    gr.clear()


def main():
    parser = argparse.ArgumentParser()
    add_commit_args(parser, default=False)
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()
    Cerebrum.logutils.autoconf('cronjob', args)

    db = Factory.get('Database')()
    db.cl_init(change_program='populate-azure-groups.py')

    sync_group(db, "it-uio-ms365-student",
               include_groups=["meta-student-900000"],
               exclude_groups=["it-uio-ms365-betalende"],
               commit=args.commit)
    sync_group(db, "it-uio-ms365-ansatt",
               include_groups=["meta-ansatt-vitenskapelig-900000",
                               "meta-ansatt-tekadm-900000"],
               exclude_groups=["it-uio-ms365-betalende", "it-uio-ms365-student"],
               commit=args.commit)
    sync_group(db, "it-uio-ms365-andre",
               include_groups=["meta-ansatt-bilag-900000",
                               "meta-tilknyttet-900000"],
               exclude_groups=["it-uio-ms365-betalende", "it-uio-ms365-student",
                               "it-uio-ms365-ansatt"],
               commit=args.commit)


if __name__ == "__main__":
    main()
