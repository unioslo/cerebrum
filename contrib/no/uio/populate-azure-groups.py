#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2007-2025 University of Oslo, Norway
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
from Cerebrum.group import group_sync

logger = logging.getLogger(__name__)


class MemberBuilder(object):

    def __init__(self, db):
        self.db = db
        self.group_cache = {}
        self.account_cache = group_sync.AccountOwnerCache(db)

    def calculate_members(
            self,
            include,
            exclude,
            member_type="person",
            intersect=False,
            exclude_quarantined=False):
        """
        Calculate a set of member ids from existing groups.

        :param include:
            Group names to include members from

        :param exclude:
            Group names to exclude members from

        :param member_type:
            Normalize members to personal account owners

        :param exclude_quarantined:
            Exclude quarantined accounts / persons with quarantined primary
            account.

        :param intersect:
            Calculate `set(include_members) & set(exclude_members)` rather than
            `set(include_members) - set(exclude_members)`
        """

        include_members = set()
        for group_name in include:
            include_members.update(
                group_sync.find_effective_members(
                    get_group_by_name(self.db, group_name)))

        exclude_members = set()
        for group_name in exclude:
            exclude_members.update(
                group_sync.find_effective_members(
                    get_group_by_name(self.db, group_name)))

        if member_type == "person":
            # include_members = set(
            #     self.account_cache.only_persons(include_members)
            # )
            exclude_members = set(
                self.account_cache.only_persons(exclude_members)
            )
        else:
            raise ValueError("invalid member type: " + repr(member_type))

        if exclude_quarantined:
            include_members = set(
                self.account_cache.exclude_quarantined(include_members,
                                                       exclude_persons=True)
            )

        wanted = set()

        if intersect:
            wanted = include_members.intersection(exclude_members)
        else:
            wanted = include_members - exclude_members

        return group_sync.get_member_ids(wanted)

    def sync_group(self, db, group_name, include_groups=None,
                   exclude_groups=None, exclude_quarantined=False,
                   intersection=False):
        group = get_group_by_name(self.db, group_name)

        wanted = self.calculate_members(
            include=(include_groups or []),
            exclude=(exclude_groups or []),
            member_type="person",
            intersect=intersection,
            exclude_quarantined=exclude_quarantined,
        )

        group_sync.set_group_members(group, wanted)


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
        mems -= set(m for m in mems if is_quarantined(db, m))

    return mems


def get_persons(db, members):
    """
    If any of the entity_ids of members belong to account objects, replace it
    in the output with the owner_id of this account.
    """
    ac = Factory.get('Account')(db)
    owners = set()

    for member in members:
        owner = member
        ac.clear()
        try:
            ac.find(member)
            owner = ac.owner_id
        except Exception:
            pass
        owners.add(owner)

    return owners


def get_group_by_name(db, group_name):
    gr = Factory.get('Group')(db)
    gr.find_by_name(group_name)
    return gr


def sync_group(db, target_group, include_groups=None, exclude_groups=None,
               exclude_quarantined=False, intersection=False):
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
    :param boolean intersection: Treats include_groups and exclude_groups
    as two sets and populates target_group with members of the intersection
    of these two groups
    """
    logger.info("Syncing group %s", target_group)

    gr = get_group_by_name(db, target_group)

    include_group_members = set()
    if include_groups:
        for include_group in include_groups:
            include_group_members.update(
                get_members(db, include_group,
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

    wanted_members = set()
    if intersection:
        wanted_members = include_group_members.intersection(
            exclude_group_members
        )
    else:
        wanted_members = include_group_members - exclude_group_members

    group_sync.set_group_members(gr, wanted_members)
    return wanted_members


def main():
    parser = argparse.ArgumentParser()
    add_commit_args(parser, default=False)
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()
    Cerebrum.logutils.autoconf('cronjob', args)

    db = Factory.get('Database')()
    db.cl_init(change_program='populate-azure-groups.py')

    sync_group = MemberBuilder(db).sync_group

    #
    # Main ms365 lincense categories: betalende -> ansatt -> student -> andre
    #
    # "betalende" are manually maintained in a it-*-ms365-betalende group
    # hierarchy, and (semi-)normalized to it-uio-ms365-betalende-utflatet.
    #
    # TODO: Move (and improve) normalization here?
    #
    sync_group(
        db, "it-uio-ms365-ansatt",
        include_groups=[
           "meta-ansatt-vitenskapelig-900000",
           "meta-ansatt-tekadm-900000",
        ],
        exclude_groups=[
            "it-uio-ms365-betalende-utflatet",
        ],
        # member_type="person",
        exclude_quarantined=True,
    )
    sync_group(
        db, "it-uio-ms365-student",
        include_groups=["meta-student-900000"],
        exclude_groups=[
            "it-uio-ms365-betalende-utflatet",
            "it-uio-ms365-ansatt",
        ],
    )
    sync_group(
        db, "it-uio-ms365-andre",
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

    # A group of members that have been excluded from the amin categories due
    # to quarantines
    sync_group(
        db, "it-uio-ms365-quarantine",
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
        db, "it-uio-ms365-ansatt-publisert",
        include_groups=["it-uio-ms365-ansatt"],
        exclude_groups=["DFO-elektroniske-reservasjoner"],
    )

    #
    # Exchange Online migration groups
    #
    # As accounts are migrated - they are added to postmaster-eo-migrerte.
    # These groups categorizes accounts according to their main group and
    # exchange online status
    #
    sync_group(
        db, "it-uio-ms365-student-u-exo",
        include_groups=["it-uio-ms365-student"],
        exclude_groups=["postmaster-eo-migrerte"],
    )
    sync_group(
        db, "it-uio-ms365-student-m-exo",
        include_groups=["it-uio-ms365-student"],
        exclude_groups=["postmaster-eo-migrerte"],
        intersection=True,
    )

    sync_group(
        db, "it-uio-ms365-betalende-u-exo",
        include_groups=["it-uio-ms365-betalende-utflatet"],
        exclude_groups=["postmaster-eo-migrerte"],
    )
    sync_group(
        db, "it-uio-ms365-betalende-m-exo",
        include_groups=["it-uio-ms365-betalende-utflatet"],
        exclude_groups=["postmaster-eo-migrerte"],
        intersection=True,
    )

    sync_group(
        db, "it-uio-ms365-andre-u-exo",
        include_groups=["it-uio-ms365-andre"],
        exclude_groups=["postmaster-eo-migrerte"],
    )
    sync_group(
        db, "it-uio-ms365-andre-m-exo",
        include_groups=["it-uio-ms365-andre"],
        exclude_groups=["postmaster-eo-migrerte"],
        intersection=True,
    )

    if args.commit:
        db.commit()
        logger.info("Committed changes")
    else:
        db.rollback()
        logger.info("Dryrun mode, rolling back changes")


if __name__ == "__main__":
    main()
