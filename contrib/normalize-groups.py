#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2020-2025 University of Oslo, Norway
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
Create/update group from group hierarchy.

This script finds all effective members of a group hierarchy (i.e. both
direct and indirect members), and creates a new group with only direct
non-group members.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import logging

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.group import group_sync
from Cerebrum.Utils import Factory
from Cerebrum.utils import argutils
from Cerebrum.utils import aggregate

logger = logging.getLogger(__name__)


def format_description(name):
    return "Flattened copy of group '{}'".format(name)


def sync_members(db, source, dest, transform_members):
    """
    Sync recursive memberships from one group to another.

    :param db:
    :param source: Group to get memberships from.
    :param dest: Group to update.
    :param transform_members:
        A function that translates an iterable of (member_id, member_type)
        tuples to a normalized list of member tuples.
    """
    logger.info("sync group members from %s (%d) to %s (%d)",
                source.group_name, source.entity_id,
                dest.group_name, dest.entity_id)

    # `find_effective_members` recursively finds all non-expired members and
    # subgroup members - as member tuples (entity-id, entity-type)
    source_members = group_sync.find_effective_members(source)

    dest_members = group_sync.get_member_ids(transform_members(source_members))
    group_sync.set_group_members(dest, dest_members)


def map_noop(db):
    """ do not transform members from the source group. """
    return group_sync.transform_noop


def map_primary(db):
    """ map all persons/personal accounts to their owners primary account. """
    return group_sync.AccountOwnerCache(db).only_primary_accounts


def map_persons(db):
    """ map all personal accounts to their owner. """
    return group_sync.AccountOwnerCache(db).only_persons


def get_group_by_name(db, group_name):
    group = Factory.get("Group")(db)
    group.find_by_name(group_name)
    return group


def parse_mapping(value):
    source, sep, dest = value.partition(":")
    if not sep:
        raise ValueError("invalid mapping: %s (expeceted <source>:<dest>)"
                         % repr(value))
    if not source:
        raise ValueError("invalid mapping source: " + repr(value))
    if not dest:
        raise ValueError("invalid mapping destination: " + repr(value))
    return source, dest


def prepare_group_map(db, raw_mappings):
    """
    Parse group mappings and find source groups.

    :type db: Cerebrum.database.Database
    :type raw_mappings: list[str]
    :param raw_mappings: a sequence of "source:destination" strings

    :returns generator: generates (source-group, destination-name) tuples.
    """
    group_map = [parse_mapping(m) for m in raw_mappings]

    # If the same source is used twice, we effectively make the same group
    # twice - we *probaly* don't want that
    repeated_src = list(
        aggregate.unique(aggregate.duplicates(t[0] for t in group_map)))
    if repeated_src:
        logger.warning("Repeated source groups: %s",
                       ", ".join(repeated_src))

    # We *could* allow creating the same destination group twice, but it
    # would cause a lot of extra work, and a bunch of group:mod changelog
    # entries for no reason.  Let's make it an error:
    repeated_dest = list(
        aggregate.unique(aggregate.duplicates(t[1] for t in group_map)))
    if repeated_dest:
        raise ValueError("Repeated destination groups: "
                         + ", ".join(repeated_dest))

    # Replace source_name with the actual group
    for source_name, dest_name in group_map:
        if source_name == dest_name:
            # Try to avoid an easy typo
            raise ValueError("Source and destination is the same group")
        source_group = get_group_by_name(db, source_name)
        yield source_group, dest_name


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Create a single group from a group hierarchy",
    )
    parser.add_argument(
        "-m", "--mapping",
        action="append",
        dest="groups",
        required=True,
        help="Add members in S to flat group D (can be repeated)",
        metavar="S:D",
    )

    # Member transform options
    transform_mutex = parser.add_argument_group(
        "members",
        "Optionally map members to ensure they are all the same type",
    ).add_mutually_exclusive_group()
    transform_mutex.set_defaults(member_transform=map_noop),
    transform_mutex.add_argument(
        "--same",
        dest="member_transform",
        action="store_const",
        const=map_noop,
        help="No transform - copy members as-is (default)",
    )
    transform_mutex.add_argument(
        "--only-primary-accounts",
        dest="member_transform",
        action="store_const",
        const=map_primary,
        help=(
            "Only include primary accounts - "
            "will map persons and personal accounts to their primary account"
        ),
    )
    transform_mutex.add_argument(
        "--only-persons",
        dest="member_transform",
        action="store_const",
        const=map_persons,
        help=(
            "Only include persons - "
            "will map personal accounts to their owner"
        ),
    )
    Cerebrum.logutils.options.install_subparser(parser)
    argutils.add_commit_args(parser)

    args = parser.parse_args(argv)
    default_log_preset = "cronjob" if args.commit else "console"
    Cerebrum.logutils.autoconf(default_log_preset, args)

    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    db = Factory.get("Database")()
    db.cl_init(change_program=parser.prog)

    transform = args.member_transform(db)

    # Go through args.groups ("source_name:dest_name" strings) and ensure that
    # the content is sane
    group_map = list(prepare_group_map(db, args.groups))
    if not group_map:
        raise ValueError("No mapping given")

    # Create/update dest group and dest members
    for source_group, dest_name in group_map:
        dest_description = format_description(source_group.group_name)
        dest_group = group_sync.assert_derived_group(db, dest_name,
                                                     dest_description)
        sync_members(db, source_group, dest_group, transform)

    if args.commit:
        logger.info("Committing changes")
        db.commit()
    else:
        db.rollback()
        logger.info("Changes rolled back (dryrun)")

    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
