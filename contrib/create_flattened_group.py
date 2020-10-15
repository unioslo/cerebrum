#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
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
Create/update group from group hierarchy.

This script extracts all direct and indirect members of a group and produces a
flattened version thereof.
"""
import argparse
import logging

import cereconf
from Cerebrum import Errors
from Cerebrum import logutils
from Cerebrum.Account import Account
from Cerebrum.Utils import Factory
from Cerebrum.utils import argutils

logger = logging.getLogger(__name__)


def get_creator(db):
    """ Get creator account for new objects. """
    creator_name = cereconf.INITIAL_ACCOUNTNAME
    logger.debug('fetching creator account %r', creator_name)
    creator = Account(db)
    creator .find_by_name(creator_name)
    logger.debug('found creator account_id=%d', creator.entity_id)
    return creator


def assert_group(db, name, source_hint):
    """Ensure that a derived group exists and is up to date."""
    co = Factory.get('Constants')(db)
    gr = Factory.get('Group')(db)

    visibility = co.group_visibility_all
    description = "Flattened copy of group '{}'".format(source_hint)
    group_type = co.group_type_derived
    try:
        gr.find_by_name(name)
        logger.info('Updating group %r', name)
        gr.populate(
            creator_id=gr.creator_id,
            visibility=visibility,
            name=gr.group_name,
            group_type=group_type,
            description=description,
        )
    except Errors.NotFoundError:
        logger.info('Creating group %r', name)
        creator = get_creator(db)
        gr.populate(
            creator_id=creator.entity_id,
            visibility=visibility,
            name=name,
            description=description,
            group_type=group_type,
        )
    logger.debug('write_db(): %r', gr.write_db())
    return gr


def transform_members(iterable, transform):
    """ Transform an iterable of (member_type, member_id) values. """
    # this is essentially just filter() and map()
    for member_type, member_id in iterable:
        result_type, result_id = transform(member_type, member_id)
        if result_type:
            yield result_type, result_id


def sync_members(db, source_group, dest_group, member_transform):
    """
    Sync recursive memberships from one group to another.

    :param db:

    :param source_group:
        Group to copy memberships from.  We will search this group for all
        recursive members.

    :param dest_group:
        Group to update.  This group will be updated to mirror all members of
        ``source_group``.

    :param member_transform:
        A function that translates (member_type, member_id) before updating
        ``dest_group``.  If the function returns (None, None) the membership
        is omitted.
    """
    logger.info("syncing group members from '%s' to '%s'",
                source_group.group_name, dest_group.group_name)
    co = Factory.get('Constants')(db)
    gr = Factory.get('Group')(db)

    logger.debug('fetching members of group %r', dest_group.group_name)
    current_members = set(
        (m['member_type'], m['member_id'])
        for m in gr.search_members(group_id=dest_group.entity_id,
                                   member_filter_expired=False))
    logger.info('found %d members of group %r',
                len(current_members), dest_group.group_name)

    logger.debug('fetching members of group %r', source_group.group_name)
    source_members = set(
        (m['member_type'], m['member_id'])
        for m in gr.search_members(group_id=source_group.entity_id,
                                   indirect_members=True,
                                   member_filter_expired=True)
        if m['member_type'] != co.entity_group)
    logger.info('found %d members of group %r',
                len(source_members), source_group.group_name)

    wanted_members = set(transform_members(source_members, member_transform))

    to_add = wanted_members - current_members
    to_remove = current_members - wanted_members

    logger.info('updating %r group members (add: %d, remove: %d)',
                dest_group.group_name, len(to_add), len(to_remove))

    for m_type, member_id in to_remove:
        dest_group.remove_member(member_id)
    for _, member_id in to_add:
        dest_group.add_member(member_id)


def noop_transform(db):
    """
    Default noop member transform.

    This transform is used when no member_type conversion is performed, and
    members are copied as-is.
    """

    def get_member(member_type, member_id):
        return member_type, member_id

    return get_member


def personal_account_transform(db):
    """
    Swap member_type=person with their primary account.

    ..note::
        All other member_type values are omitted.
    """
    ac = Factory.get('Account')(db)
    co = Factory.get('Constants')(db)
    primary_accounts = {}

    logger.info('Caching primary accounts')
    for row in ac.list_accounts_by_type(primary_only=True):
        primary_accounts[row['person_id']] = row['account_id']

    def get_member(member_type, member_id):
        if member_type == co.entity_person:
            if member_id in primary_accounts:
                return co.entity_account, primary_accounts[member_id]
        return None, None

    return get_member


def person_transform(db):
    """
    Swap any member_type=account with their owner (person)
    """
    ac = Factory.get('Account')(db)
    co = Factory.get('Constants')(db)

    owners = {}

    logger.info('Caching account owners')
    for row in ac.search(owner_type=co.entity_person):
        owners[row['account_id']] = row['owner_id']

    def get_member(member_type, member_id):
        if member_type == co.entity_person:
            return member_type, member_id
        if member_type == co.entity_account:
            if member_id in owners:
                return co.entity_person, owners[member_id]
        return None, None

    return get_member


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Create a single group from a group hierarchy',
    )
    parser.add_argument(
        '-t', '--target-group',
        dest='source_name',
        required=True,
        default=None,
        help='Group to fetch members from (flatten)'
    )
    parser.add_argument(
        '-d', '--destination-group',
        dest='dest_name',
        required=True,
        default=None,
        help='Destination group (flattened copy)',
    )

    # Member transform options
    member_desc = parser.add_argument_group(
        'members',
        'Change which members will be included.'
    )
    member_types = member_desc.add_mutually_exclusive_group()
    member_types.set_defaults(member_transform=noop_transform)
    member_types.add_argument(
        '--same',
        dest='member_transform',
        action='store_const',
        const=noop_transform,
        help='No change (this is the default)',
    )
    member_types.add_argument(
        '--only-primary-accounts',
        dest='member_transform',
        action='store_const',
        const=personal_account_transform,
        help=('Only include personal, primary accounts'
              ' (i.e. translate persons to accounts)'),
    )
    member_types.add_argument(
        '--only-persons',
        dest='member_transform',
        action='store_const',
        const=person_transform,
        help='Only include persons (will translate account to owners)',
    )

    logutils.options.install_subparser(parser)

    argutils.add_commit_args(parser, default=False)
    args = parser.parse_args(inargs)
    logutils.autoconf('cronjob', args)

    logger.info('Start %s', parser.prog)
    logger.debug('args: %r', args)

    db = Factory.get('Database')()
    db.cl_init(change_program=parser.prog)

    source = Factory.get('Group')(db)
    try:
        source.find_by_name(args.source_name)
    except Errors.NotFoundError:
        parser.error(
            'Target group {} does not exist.'.format(args.source_name))

    transform = args.member_transform(db)

    dest = assert_group(db, name=args.dest_name, source_hint=source.group_name)

    sync_members(db, source, dest, transform)

    if args.commit:
        logger.info("Committing changes")
        db.commit()
    else:
        db.rollback()
        logger.info("Changes rolled back (dryrun)")

    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
