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
and it-uio-ms365-andre determine licences in AzureAD. AzureAD cannot handle
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


def is_quarantined(db, entity_id):
    """
    Return whether an account, or a Person's primary account,
    is quarantined or not.
    """
    co = Factory.get('Constants')(db)
    en = Factory.get('Entity')(db)
    ac = Factory.get('Account')(db)

    en.find(entity_id)

    if en.entity_type == co.entity_account:
        ac.find(entity_id)
    elif en.entity_type == co.entity_person:
        pe = Factory.get('Person')(db)
        pe.find(entity_id)
        try:
            ac.find(pe.get_primary_account())
        except Cerebrum.Errors.NotFoundError:
            return False
    else:
        return False

    return bool(ac.get_entity_quarantine(only_active=True))


def get_members(db, group_name, indirect_members=False,
                filter_expired=True, filter_groups=False,
                filter_quarantined=False):
    """ Return, as a set, the member_ids of a given group """
    co = Factory.get('Constants')(db)
    gr = Factory.get('Group')(db)
    gr.find_by_name(group_name)
    if filter_groups:
        mems = {
            m['member_id']
            for m in gr.search_members(group_id=gr.entity_id,
                                       indirect_members=indirect_members,
                                       member_filter_expired=filter_expired)
            if m['member_type'] != co.entity_group
        }
    else:
        mems = {
            m['member_id']
            for m in gr.search_members(group_id=gr.entity_id,
                                       indirect_members=indirect_members,
                                       member_filter_expired=filter_expired)
        }
    if filter_quarantined:
        mems -= { m for m in mems if is_quarantined(db, m) }

    return mems


def get_persons(db, members):
    """
    If any of the entity_ids of members belong to account objects, replace it
    in the output with the owner_id of this account.
    """
    ac = Factory.get('Account')(db)
    gr = Factory.get('Group')(db)
    co = Factory.get('Constants')(db)
    owners = set()

    for member in members:
        owner = member
        ac.clear()
        try:
            ac.find(member)
            owner = ac.owner_id
        except:
            pass
        owners.add(owner)

    return owners


def sync_group(db, target_group, include_groups=None, exclude_groups=None,
               exclude_quarantined=False):
    """
    Update members of target group, based on membership in other groups.

    :param Cerebrum.database.Database db: A Database object.
    :param str target_group: Target group.
    :param list include_groups: Members from these groups are added to
    target group.
    :param list exclude_groups: Members from these groups are not added to
    target group, even if members of include_groups.
    :param list exclude_quarantined: Members with quarantines are not added
    to target group, even if members of include_groups.
    """
    logger.info("Syncing group %s", target_group)

    gr = Factory.get('Group')(db)

    include_group_members = set()
    if include_groups:
        for include_group in include_groups:
            include_group_members.update(get_members(db, include_group,
                                                     indirect_members=True,
                                                     filter_groups=True,
                                                     filter_quarantined=exclude_quarantined))
        logger.debug("Found %s members of %s", len(include_group_members),
                    include_groups)

    exclude_group_members = set()
    if exclude_groups:
        for exclude_group in exclude_groups:
            exclude_group_members.update(get_members(db, exclude_group,
                                                     indirect_members=True))
        logger.debug("Found %s members of %s", len(exclude_group_members),
                    exclude_groups)

    # This step is needed to sanitise the contents of 'it-uio-ms365-betalende'
    exclude_group_members = get_persons(db, exclude_group_members)

    gr.find_by_name(target_group)
    current_members = get_members(db, target_group)
    logger.debug("%s has %s current members", target_group, len(current_members))

    # Add any member in include groups, not already present in target group
    add_members = include_group_members - exclude_group_members - current_members
    logger.info("Adding %s new members to %s", len(add_members), target_group)
    for member in add_members:
        gr.add_member(member)
        logging.debug('Added new member %r to group %r', member, target_group)

    # Remove any member from target group that is no loger present in the
    # include_groups OR any member of target group that is also a member of
    # the exclude_groups
    remove_members = current_members - (include_group_members -
                                        exclude_group_members)
    logger.info("Removing %s members from %s", len(remove_members), target_group)
    for member in remove_members:
        gr.remove_member(member)
        logging.debug('Removed member %r from group %r', member, target_group)

    gr.clear()


def main():
    parser = argparse.ArgumentParser()
    add_commit_args(parser, default=False)
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()
    Cerebrum.logutils.autoconf('cronjob', args)

    db = Factory.get('Database')()
    db.cl_init(change_program='populate-azure-groups.py')

    sync_group(db, "it-uio-ms365-ansatt",
               include_groups=["meta-ansatt-vitenskapelig-900000",
                               "meta-ansatt-tekadm-900000"],
               exclude_quarantined=True,
               exclude_groups=["it-uio-ms365-betalende-utflatet"])
    sync_group(db, "it-uio-ms365-student",
               include_groups=["meta-student-900000"],
               exclude_groups=["it-uio-ms365-betalende-utflatet",
                               "it-uio-ms365-ansatt"])
    sync_group(db, "it-uio-ms365-andre",
               include_groups=["meta-ansatt-bilag-900000",
                               "meta-tilknyttet-900000"],
               exclude_quarantined=True,
               exclude_groups=["it-uio-ms365-betalende-utflatet",
                               "it-uio-ms365-student",
                               "it-uio-ms365-ansatt"])
    sync_group(db, "it-uio-ms365-quarantine",
               include_groups=["meta-ansatt-bilag-900000",
                               "meta-tilknyttet-900000"],
               exclude_groups=["it-uio-ms365-betalende-utflatet",
                               "it-uio-ms365-student",
                               "it-uio-ms365-ansatt",
                               "it-uio-ms365-andre"])
    sync_group(db, "it-uio-ms365-ansatt-publisert",
               include_groups=["it-uio-ms365-ansatt"],
               exclude_groups=["DFO-elektroniske-reservasjoner"])

    if args.commit:
        db.commit()
        logger.info("Committed changes")
    else:
        db.rollback()
        logger.info("Dryrun mode, rolling back changes")


if __name__ == "__main__":
    main()
