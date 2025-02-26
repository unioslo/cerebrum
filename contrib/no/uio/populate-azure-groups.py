#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2022-2025 University of Oslo, Norway
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
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.group import group_sync

logger = logging.getLogger(__name__)


def get_group_by_name(db, group_name):
    gr = Factory.get('Group')(db)
    gr.find_by_name(group_name)
    return gr


class MembershipBuilder(object):

    def __init__(self, db):
        self.db = db
        self.group_cache = {}
        self.account_cache = group_sync.AccountOwnerCache(db)

    def calculate_members(
            self,
            include_groups=None,
            exclude_groups=None,
            member_type=None,
            intersect=False,
            exclude_quarantined=False):
        """
        Calculate a set of member ids from existing groups.

        :param include_groups:
            Group names to include members from

        :param exclude_groups:
            Group names to exclude members from

        :param member_type:
            Optionally normalize membership to *person* or *primary* account

        :param exclude_quarantined:
            Exclude quarantined accounts / persons with quarantined primary
            account.

        :param intersect:
            Calculate `set(include_members) & set(exclude_members)` rather than
            `set(include_members) - set(exclude_members)`.

            This can be used to create a secondary "mirrored" group that only
            contains members that are explicitly excluded from the "normal"
            group.
        """
        if member_type is None:
            transform = group_sync.transform_noop
        elif member_type == "person":
            transform = self.account_cache.only_persons
        elif member_type == "primary":
            transform = self.account_cache.only_primary_accounts
        else:
            raise ValueError("invalid member_type: " + repr(member_type))

        # collect members from include_groups and exclude_groups
        include_members = set()
        for group_name in (include_groups or []):
            include_members.update(
                group_sync.find_effective_members(
                    get_group_by_name(self.db, group_name)))

        exclude_members = set()
        for group_name in (exclude_groups or []):
            exclude_members.update(
                group_sync.find_effective_members(
                    get_group_by_name(self.db, group_name)))

        # normalize members
        include_members = set(transform(include_members))
        exclude_members = set(transform(exclude_members))

        if exclude_quarantined:
            # omit quarantined accounts or persons with quarantined
            # primary accounts
            include_members = set(
                self.account_cache.exclude_quarantined(include_members,
                                                       exclude_persons=True)
            )

        # calculate memberships and return a set of entity-id values
        if intersect:
            wanted = include_members.intersection(exclude_members)
        else:
            wanted = include_members - exclude_members
        return group_sync.get_member_ids(wanted)

    def sync_group(self, group_name, member_type="person",
                   include_groups=None, exclude_groups=None,
                   exclude_quarantined=False, intersect=False):
        group = get_group_by_name(self.db, group_name)

        wanted = self.calculate_members(
            member_type=member_type,
            include_groups=include_groups,
            exclude_groups=exclude_groups,
            intersect=intersect,
            exclude_quarantined=exclude_quarantined,
        )

        group_sync.set_group_members(group, wanted)


def main():
    parser = argparse.ArgumentParser()
    add_commit_args(parser, default=False)
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()
    Cerebrum.logutils.autoconf('cronjob', args)

    db = Factory.get('Database')()
    db.cl_init(change_program='populate-azure-groups.py')

    sync_group = MembershipBuilder(db).sync_group

    #
    # Main ms365 lincense categories: betalende -> ansatt -> student -> andre
    #
    # "betalende" are manually maintained in a `it-*-ms365-betalende` group
    # hierarchy, and (semi-)normalized to `it-uio-ms365-betalende-utflatet`.
    #
    # TODO: Move (and improve) normalization of
    # `it-uio-ms365-betalende-utflatet` here?
    #
    sync_group(
        "it-uio-ms365-ansatt",
        member_type="person",
        include_groups=[
           "meta-ansatt-vitenskapelig-900000",
           "meta-ansatt-tekadm-900000",
        ],
        exclude_groups=[
            "it-uio-ms365-betalende-utflatet",
        ],
        exclude_quarantined=True,
    )
    sync_group(
        "it-uio-ms365-student",
        member_type="person",
        include_groups=["meta-student-900000"],
        exclude_groups=[
            "it-uio-ms365-betalende-utflatet",
            "it-uio-ms365-ansatt",
        ],
    )
    sync_group(
        "it-uio-ms365-andre",
        member_type="person",
        include_groups=[
            "meta-ansatt-bilag-900000",
            "meta-tilknyttet-900000",
        ],
        exclude_groups=[
            "it-uio-ms365-betalende-utflatet",
            "it-uio-ms365-student",
            "it-uio-ms365-ansatt",
        ],
        exclude_quarantined=True,
    )

    #
    # A group of members that have been excluded from the main categories due
    # to quarantines
    #
    # TODO: This is currently only persons excluded from it-uio-ms365-andre -
    # why not those excluded from it-uio-ms365-ansatt?
    #
    sync_group(
        "it-uio-ms365-quarantine",
        member_type="person",
        include_groups=[
            "meta-ansatt-bilag-900000",
            "meta-tilknyttet-900000",
        ],
        exclude_groups=[
            "it-uio-ms365-betalende-utflatet",
            "it-uio-ms365-student",
            "it-uio-ms365-ansatt",
            "it-uio-ms365-andre",
        ],
    )

    #
    # The main employee group, but only with non-hidden employees
    #
    sync_group(
        "it-uio-ms365-ansatt-publisert",
        member_type="person",
        include_groups=["it-uio-ms365-ansatt"],
        exclude_groups=["DFO-elektroniske-reservasjoner"],
    )

    #
    # Exchange Online (exo) migration groups
    #
    # As accounts are migrated to exo, they are added to
    # `postmaster-eo-migrerte`.  These groups categorizes persons according to
    # their main group and exo status.
    #
    sync_group(
        "it-uio-ms365-student-u-exo",
        member_type="person",
        include_groups=["it-uio-ms365-student"],
        exclude_groups=["postmaster-eo-migrerte"],
    )
    sync_group(
        "it-uio-ms365-student-m-exo",
        member_type="person",
        include_groups=["it-uio-ms365-student"],
        exclude_groups=["postmaster-eo-migrerte"],
        intersect=True,
    )

    sync_group(
        "it-uio-ms365-betalende-u-exo",
        member_type="person",
        include_groups=["it-uio-ms365-betalende-utflatet"],
        exclude_groups=["postmaster-eo-migrerte"],
    )
    sync_group(
        "it-uio-ms365-betalende-m-exo",
        member_type="person",
        include_groups=["it-uio-ms365-betalende-utflatet"],
        exclude_groups=["postmaster-eo-migrerte"],
        intersect=True,
    )

    sync_group(
        "it-uio-ms365-andre-u-exo",
        member_type="person",
        include_groups=["it-uio-ms365-andre"],
        exclude_groups=["postmaster-eo-migrerte"],
    )
    sync_group(
        "it-uio-ms365-andre-m-exo",
        member_type="person",
        include_groups=["it-uio-ms365-andre"],
        exclude_groups=["postmaster-eo-migrerte"],
        intersect=True,
    )

    if args.commit:
        db.commit()
        logger.info("Committed changes")
    else:
        db.rollback()
        logger.info("Dryrun mode, rolling back changes")


if __name__ == "__main__":
    main()
