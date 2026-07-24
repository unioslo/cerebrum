#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2012-2026 University of Oslo, Norway
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
Populate simple groups from affiliations.

Note that this script does *not* create groups - any group targeted by this
script must already exsist in Cerebrum.

The groups to update either comes from `ocnfiguration`_, or from command-line
arguments.


Configuration
-------------
If --use-config is provided on the command line,  the script will attempt to
use the mapping in ``cereconf.AFFILIATION_GROUPS``.

This value maps affiliations to group names in the same way that the
`-a` option.  Example:
::

    AFFILIATION_GROUPS = {
      'ANSATT': 'affiliation-ansatt',
      'TILKNYTTET': 'affiliation-tilknyttet',
      'STUDENT': 'affiliation-student',
      'MANUELL': 'affiliation-manuell',
    }
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import logging
import textwrap

import six

import cereconf
import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.group import group_sync
from Cerebrum.database.ctx import db_context
from Cerebrum.Utils import Factory
from Cerebrum.utils import argutils

logger = logging.getLogger(__name__)


def get_mapping(db, raw_mapping):
    """
    Look up and validate the mappings from *pairs*.

    :param db:

    :type mappings: Iterable[tuple[str,str]]
    :param mappings:
        An iterable of (affiliation-name, group-name) pairs.

    :rtype: list[tuple[obj,obj]]
    :returns:
        A list of (affiliation, group) pairs

        - The *affiliation* is the affiliation code to use
        - The *group* is the actual group entity to update

    :raises ValueError: if any input mapping pairs are invalid
    """
    const = Factory.get("Constants")(db)
    seen_groups = set()
    mapping = []
    for raw_aff, raw_group in raw_mapping:
        raw_pair = ":".join((raw_aff, raw_group))
        try:
            aff, status = const.get_affiliation(raw_aff)
        except LookupError as e:
            raise ValueError("Unknown affilation %s (%s)"
                             % (e, raw_pair))
        if status is not None:
            raise ValueError("AFF/status is not supported (%s)" % (raw_pair,))

        group = Factory.get("Group")(db)
        try:
            group.find_by_name(raw_group)
        except Errors.NotFoundError:
            raise ValueError("Unknown group %s (%s)"
                             % (raw_group, raw_pair))
        if group.entity_id in seen_groups:
            raise ValueError("Duplicate group %s (%s)",
                             group.group_name, raw_pair)
        seen_groups.add(group.entity_id)

        mapping.append((aff, group))

    return sorted(mapping, key=lambda p: six.text_type(p[0]))


class PrimaryAccountLookup(object):
    """ Get primary accounts from affiliations. """

    def __init__(self, db):
        self.db = db
        self.cache = group_sync.AccountOwnerCache(db)
        self.const = Factory.get("Constants")(db)

    def _get_people(self, affiliation):
        pe = Factory.get("Person")(self.db)
        return set(row['person_id'] for row in
                   pe.list_affiliations(affiliation=int(affiliation)))

    def _person_to_primary(self, person_ids):
        return group_sync.get_member_ids(
            self.cache.only_primary_accounts(
                (person_id, self.const.entity_person)
                for person_id in person_ids
            ))

    def __call__(self, affiliation):
        person_ids = self._get_people(affiliation)
        logger.info("Found %d persons with affiliation %s",
                    len(person_ids), six.text_type(affiliation))
        accounts = self._person_to_primary(person_ids)
        logger.info("Found %d primary accounts with affiliation %s",
                    len(accounts), six.text_type(affiliation))
        return accounts


def update_groups(db, mappings):
    """ Update groups according to the input mappings. """
    get_primary_accounts = PrimaryAccountLookup(db)

    for affiliation, group in mappings:
        logger.info("Building group %s (%d) from affiliation %s",
                    group.group_name, group.entity_id,
                    six.text_type(affiliation))
        members = get_primary_accounts(affiliation)
        group_sync.set_group_members(group, members)


def _mapping_arg(value):
    aff, group = value.split(":")
    return aff, group


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Update affiliation groups",
        epilog=textwrap.dedent(
            """
            Update group memberships for primary accounts based on
            affiliations.
            """
        ).lstrip(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="List affilations and exit",
    )

    map_args = parser.add_mutually_exclusive_group(required=True)
    map_args.add_argument(
        "--use-config",
        action="store_true",
        dest="use_config",
        help="Read mappings from cereconf.AFFILIATION_GROUPS",
    )
    map_args.add_argument(
        "-a", "--affmap",
        action="append",
        dest="mapping_pairs",
        type=_mapping_arg,
        help="Add a mapping from <aff> to <group>",
        metavar="<aff:group>",
    )

    argutils.add_commit_args(parser)
    log_subparser = Cerebrum.logutils.options.install_subparser(parser)
    log_subparser.set_defaults(**{
        Cerebrum.logutils.options.OPTION_LOGGER_LEVEL: "INFO",
    })

    args = parser.parse_args(argv)
    default_preset = "cronjob" if args.commit else "console"
    Cerebrum.logutils.autoconf(default_preset, args)

    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    db = Factory.get("Database")()
    dryrun = not args.commit

    # --list - show affs and exit
    if args.list:
        const = Factory.get("Constants")(db)
        affs = const.fetch_constants(const.PersonAffiliation)
        for aff in sorted(affs, key=six.text_type):
            print("%s: %s (%s)"
                  % (int(aff), six.text_type(aff), aff.description))
        return

    # Get affiliation -> group mappings
    if args.use_config:
        logger.info("Using default mapping from cereconf.AFFILIATION_GROUPS")
        raw_pairs = list(getattr(cereconf, "AFFILIATION_GROUPS", {}).items())
    elif args.mapping_pairs:
        raw_pairs = args.mapping_pairs
    mapping = get_mapping(db, raw_pairs)
    if not mapping:
        raise ValueError("No mapping found")

    # Process mappings
    with db_context(db, dryrun):
        db.cl_init(change_program=parser.prog)
        update_groups(db, mapping)

    logger.info("Done %s", parser.prog)


if __name__ == "__main__":
    main()
