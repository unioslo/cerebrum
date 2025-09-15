#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2014-2025 University of Oslo, Norway
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
Build simple groups from affiliation types.

This script is a legacy solution for implementing simple affiliation groups.
The resulting groups will contain a list of the primary accounts for owners
with a given affiliation type.

This script is a good solution if an organization e.g. needs a single group
with all employees, but has no use for group hierarchies with groups for each
org unit.

Configuration
--------------
This script build groups for all entries in `cereconf.COLLECTION_GROUPS`.  The
setting should contain a list of `(<group>, [<affiliation>, ...])` tuples.

<group> (str)
    The name of a pre-existing group in Cerebrum.

<affiliation> (str)
    A string with a given affiliation to include in the group, optionally
    restricted to a source system or affiliation status:
    `[<source>:]<affiliation>[/<status>].

Example:
::

    COLLECTION_GROUPS = [
        ("employee-ish", ["DFO_SAP:ANSATT", "GREG:TILKNYTTET/ekst_partner"]),
        ("student-ish", ["STUDENT/aktiv", "STUDENT/ny"]),
        ("guest-ish", ["TILKNYTTET"]),
    ]


See also
---------
There are other scripts in Cerebrum for more complex groups and use cases.

`contrib/populate-automatic-groups.py`
    A more generic solution for building group hierachies from affilations.

`contrib/normalize-groups.py`
    Script for building simple, normalized groups from group hierachies.
    Memberships can be mapped to e.g. primary user accounts or all owned user
    accounts.
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
from Cerebrum.Utils import Factory
from Cerebrum.database.ctx import db_context
from Cerebrum.group import group_sync
from Cerebrum.utils.argutils import add_commit_args


logger = logging.getLogger(__name__)


def get_group_by_name(db, group_name):
    gr = Factory.get('Group')(db)
    gr.find_by_name(group_name)
    return gr


def parse_affiliation(const, value):
    """ Parse a `[<source>:]<affiliation>[/<status>]` affiliation spec. """
    source_system = None
    affiliation = None
    aff_status = None

    # extract source system
    if ":" in value:
        raw_source, raw_aff = value.split(':', 1)
        # We need to use human2constant to keep support for attr-lookups
        source_system = const.human2constant(raw_source)
        if (source_system is None
                or not isinstance(source_system, const.AuthoritativeSystem)):
            raise LookupError("Unkonwn source system %s (%s)"
                              % (repr(raw_source), repr(value)))
    else:
        raw_aff = value

    # parse affiliation
    try:
        # We need to use human2constant to keep support for attr-lookups
        tmp = const.human2constant(raw_aff)
        # tmp is either None, PersonAffiliation, PersonAffStatus, or in extreme
        # cases, the wrong constant type (e.g. someone put `"spread_foo"` in
        # the config).  Let's re-parse or validate it with
        # const.get_affiliation:
        affiliation, aff_status = const.get_affiliation(tmp or raw_aff)
    except Exception:
        raise LookupError("Unkonwn affiliation %s (%s)"
                          % (repr(raw_aff), repr(value)))

    return (source_system, affiliation, aff_status)


def prepare_config(db, config):
    """
    Validate and remap config to an iterable of groups and constants.

    :returns generator:
        yields tuples of (group, [(source, aff, status), ...]).

        - The group is the actual group object to update the memberships of.
        - The source, aff, and status are the actual constant objects to use in
          the affiliation membership search.
    """
    seen_groups = set()

    for i, (group_name, aff_specs) in enumerate(config):
        try:
            group = get_group_by_name(db, group_name)
        except Errors.NotFoundError:
            raise ValueError("invalid group name in config[%d]: %s"
                             % (i, repr(group_name)))
        if group.entity_id in seen_groups:
            raise ValueError("duplicate group name in config[%d]: %s"
                             % (i, repr(group_name)))
        seen_groups.add(group.entity_id)
        try:
            affiliations = [parse_affiliation(group.const, aff_spec)
                            for aff_spec in aff_specs]
        except LookupError as e:
            raise ValueError("invalid affiliation in config[%d]: %s" % (i, e))

        yield group, affiliations


def pretty_aff(source_system, affiliation, status):
    result = six.text_type(status or affiliation)
    if source_system:
        result = six.text_type(source_system) + ":" + result
    return result


def populate_group_memberships(group, affiliations):
    """Add and remove accounts from the group."""
    pretty_affs = ", ".join(pretty_aff(*a) for a in affiliations)
    logger.info("Updating %s (%d) with affs: %s",
                group.group_name, group.entity_id, pretty_affs)

    pe = Factory.get('Person')(group._db)
    members = set()

    # Look up affiliations
    for source, aff, status in affiliations:
        if all(v is None for v in (source, aff, status)):
            raise ValueError("empty affiliation spec")

        logger.debug("Collecting members from %s",
                     pretty_aff(source, aff, status))

        # Fetch the members from affiliation.
        lookup_args = {
            'source_system': None if source is None else int(source),
            'affiliation': None if aff is None else int(aff),
            'status': None if status is None else int(status),
            # row['person_id'] will be the primary account_id:
            'ret_primary_acc': True,
        }
        # Consider caching <aff> -> <member-list>, in case multiple groups uses
        # the same aff-criteria?
        for person in pe.list_affiliations(**lookup_args):
            # The person_id here, is acctually the account_id :S
            members.add(person['person_id'])

    group_sync.set_group_members(group, members)
    logger.info("Group %s (%d) is up-to-date",
                group.group_name, group.entity_id)


def main(argv=None):
    """Arg parsing and handling."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
            """
            Populate configured group memberships from affiliations.
            """
        ).lstrip(),
        epilog=textwrap.dedent(
            """
            Will sync memberships for the groups given in
            `cereconf.COLLECTION_GROUPS`.

            Example:

              COLLECTION_GROUPS = [
                ("uio-tilk", ["SAP:ANSATT", "FS:STUDENT",
                              "TILKNYTTET/bilag"]),
              ]

            ... will ensure that the group 'uio-tilk' is filled with primary
            accounts of persons with affiliation ANSATT from SAP, STUDENT from
            FS or TILKNYTTET/bilag from any source system.

            Any group mentioned in COLLECTION_GROUPS and processed by this
            script *must* be created manually first!
            """
        ).lstrip(),
    )
    add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(argv)

    Cerebrum.logutils.autoconf("cronjob", args)
    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    dryrun = not args.commit
    with db_context(Factory.get("Database")(), dryrun) as db:
        db.cl_init(change_program=parser.prog)

        logger.debug("Validating cereconf.COLLECTION_GROUPS")
        group_map = list(prepare_config(db, cereconf.COLLECTION_GROUPS))

        logger.debug("Populating %d groups...", len(group_map))
        for group, affs in group_map:
            populate_group_memberships(group, affs)

    logger.info("Done %s:", parser.prog)


if __name__ == "__main__":
    main()
