#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2019 University of Oslo, Norway
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
"""Remove group memberships for accounts of unaffiliated persons

This is done in the following steps:
 1. Check if the person has affiliations.
 2. If not, get all accounts owned by this person.
 3. Remove all those accounts from all groups except the account's
    default file group
    - Leave memberships to groups with types other than manual or unknown
      alone.

Potential problems:
 1. If, for whatever reason, a person does not have any affiliations, but the
    account does, the account will be removed from all groups, even though it
    may be the account that has the right affiliations. This should not be a
    serious problem and should only affect a very small amount of persons, if
    any.

"""

import argparse
import logging

import mx.DateTime
from Cerebrum import logutils
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import add_commit_args


def remove_persons(database, logger, posix_user2gid, grace_period):
    """Remove accounts of unaffiliated persons from specific groups

    :type database: Cerebrum.CLDatabase.CLDatabase
    :type logger: logging.Logger
    :param dict posix_user2gid: mapping account id to default file group
    :param int grace_period: grace period in days
    """
    persons_affected = set()
    groups_affected = set()
    group = Factory.get('Group')(database)
    account = Factory.get('Account')(database)
    const = Factory.get('Constants')(database)

    # Group types to remove members from
    group_type_remove_members = (
        int(const.group_type_manual),
        int(const.group_type_unknown),
    )

    # Cache group type of all groups
    logger.info("Caching group types of all groups")
    group_type = cache_group_types(group)

    # Find all person affiliations and filter by deletion date
    logger.info("Finding unaffiliated persons outside grace period")
    person_cache = cache_person_affs(database)

    filtered_persons = set()
    for pid, aff_del_dates in person_cache.items():
        if None in aff_del_dates:
            continue
        if not any(delete_date > mx.DateTime.now() -
                   mx.DateTime.DateTimeDeltaFromDays(grace_period)
                   for delete_date in aff_del_dates):
            filtered_persons.add(pid)

    # Find the accounts of those persons
    logger.info("Finding accounts owned by those persons")
    potential_accs = set()
    for row in account.search(owner_id=filtered_persons):
        potential_accs.add(row['account_id'])

    # Find the group memberships of those accounts and remove them
    logger.info("Removing accounts from groups")
    for row in group.search_members(member_id=potential_accs,
                                    member_type=const.entity_account):
        mid = int(row['member_id'])
        gid = int(row['group_id'])
        # Skip default file group
        if mid in posix_user2gid and gid == posix_user2gid[mid]:
            continue
        # Skip groups of the wrong type
        if group_type[gid] not in group_type_remove_members:
            continue
        logger.info("Remove account %i from group %i", mid, gid)
        persons_affected.add(mid)
        groups_affected.add(gid)
        group.remove_member_from_group(mid, gid)
    logger.info("Removed %i persons from %i groups",
                len(persons_affected), len(groups_affected))


def cache_group_types(gr):
    """Make a cache of group id to group type

    We want to use this for filtering based on group types
    """
    group_dict = {}
    for row in gr.search(filter_expired=False):
        group_dict[row["group_id"]] = row["group_type"]
    return group_dict


def cache_person_affs(database):
    """Make a cache of the delete dates of all person affiliations

    :type database: Cerebrum.CLDatabase.CLDatabase
    :return dict: mapping person id to delete date of affs
    """
    person = Factory.get('Person')(database)
    person_affs = {}
    for row in person.list_affiliations(include_deleted=True):
        pid = int(row['person_id'])
        if pid not in person_affs:
            person_affs[pid] = set()
        delete_date = row['deleted_date']
        person_affs[pid].add(delete_date)
    return person_affs


def cache_posix_dfgs(database):
    """Map account id to posix group id

    :type database: Cerebrum.CLDatabase.CLDatabase
    :return dict: mapping account id to default file group
    """
    posix_user = Factory.get('PosixUser')(database)
    posix_users = posix_user.list_posix_users()
    posix_user2gid = {}
    for row in posix_users:
        posix_user2gid[int(row['account_id'])] = int(row['gid'])
    return posix_user2gid


def main(inargs=None):
    """Parse arguments and run corresponding functions

    :param inargs: arguments to the parser
    """
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-g', '--grace',
        type=int,
        default=0,
        help="Grace period for person affiliations in days (default: 0)")
    add_commit_args(parser)

    logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    logutils.autoconf('cronjob', args)

    logger.info("Starting program '%s'", parser.prog)
    logger.info('args: %r', args)

    database = Factory.get('Database')()
    database.cl_init(change_program=parser.prog)

    # Cache default file group of users
    logger.info('Caching default file groups of users')
    posix_user2gid = cache_posix_dfgs(database)
    remove_persons(database, logger, posix_user2gid, args.grace)

    if args.commit:
        logger.info('Committing changes to database')
        database.commit()
    else:
        logger.info('Rolling back changes')
        database.rollback()

    logger.info("Finished program '%s'", parser.prog)


if __name__ == '__main__':
    main()
