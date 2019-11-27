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
"""Remove group memberships for unaffiliated users or persons

For users, this is done in the following steps:
 1. Check if the account has affiliations
 2. If not, check if it is member of any groups.
 3. If it is member of a group, remove it unless the group is the account's
    default file group.

Potential problems:
 1. If the person has an affiliation, but the account does not, the account
    will still be removed from all its groups. This can be fixed by making a
    clean up script that adds the affiliation of the person to the account, but
    this only works for persons with a single affiliation.
 2. If a person does not have any affiliations but no one has done the clean up
    on the account we will still find affiliations on the account and not do
    anything even if they technically should be removed from all groups.

 Both problems highlight the problem with setting affiliations for accounts
 manually.

For persons, this is done in the following steps:
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


def remove_accounts(database, logger, posix_user2gid):
    """Remove all accounts without account type

    :type database: Cerebrum.CLDatabase.CLDatabase
    :type logger: logging.Logger
    :param dict posix_user2gid: mapping account id to default file group
    """

    group = Factory.get('Group')(database)
    const = Factory.get('Constants')(database)

    # Select group_id and member_id of accounts with no affiliation where the
    # owner_type of the account is a person (this rules out accounts owned by
    # groups, such as guest- and system accounts.
    logger.info('Fetching candidates for deletion')
    group_rows_for_deletion = database.query(
        """
        SELECT group_id, member_id
        FROM [:table schema=cerebrum name=group_member]
        WHERE member_id IN (
            SELECT account_id
            FROM [:table schema=cerebrum name=account_info] ai
            WHERE owner_type=:owner_type AND
                  account_id NOT IN (
                      SELECT account_id
                      FROM [:table schema=cerebrum name=account_type] at
                      )
            )
        """, {'owner_type': int(const.entity_person)}
    )

    logger.info('Beginning membership deletion')
    if not group_rows_for_deletion:
        logger.info('No memberships to delete')
    for row in group_rows_for_deletion:
        # Skip default file group
        mid = row['member_id']
        gid = row['group_id']
        if mid in posix_user2gid and gid == posix_user2gid[mid]:
            continue
        logger.info("Removing account %i from group %i", mid, gid)
        group.remove_member_from_group(mid, gid)


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
    group_type = cache_group_types(database)

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


def cache_group_types(database):
    """Make a cache of group id to group type

    We want to use this for filtering based on group types
    """
    group_dict = {}
    for group_id, group_type in database.query(
        """
        SELECT group_id, group_type
        FROM [:table schema=cerebrum name=group_info]
        """
    ):
        group_dict[group_id] = group_type
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
    acc_pers = parser.add_mutually_exclusive_group()
    acc_pers.add_argument(
        '-a', '--accounts',
        action='store_true',
        help="Remove accounts from groups if accounts don't have affiliations")
    acc_pers.add_argument(
        '-p', '--persons',
        action='store_true',
        help="""Remove accounts from groups if owner of the account is a
                person and that person does not have any affiliations""")

    person_args = parser.add_argument_group("Person arguments")
    person_args.add_argument(
        '-g', '--grace',
        type=int,
        default=0,
        help="Grace period for person affiliations in days (default: 180)")
    add_commit_args(parser)

    logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    logutils.autoconf('cronjob', args)

    logger.info("Starting program '%s'", parser.prog)
    logger.info('args: %r', args)

    database = Factory.get('Database')()
    database.cl_init(change_program=parser.prog)

    if args.accounts or args.persons:
        # Cache default file group of users
        logger.info('Caching default file groups of users')
        posix_user2gid = cache_posix_dfgs(database)

        if args.accounts:
            remove_accounts(database, logger, posix_user2gid)
        if args.persons:
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
