#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2020-2026 University of Oslo, Norway
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
Build and maintain a manager groups.

These groups reflects an organization tree i Cerebrum (i.e. ou perspective).

This script simply builds a series of groups and supergroups, but does not care
about the final "leaf group" members - this is maintained by the event-driven
hr-import (see :mod:`Cerebrum.modules.no.uio.hr_import.leader_groups`).

This is similar to e.g. ``contrib/populate-automatic-groups.py``, but with a
simplified hierarchy, and without populating the "leaf groups".

Groups
=======
The groups maintained by this script falls into two categories:

Manager groups
    Group that represents manager(s) at a given org unit, named
    <prefix>-<location-code>.  This script doesn't touch memberships in these
    groups - it just creates or deletes them according to the current org tree.

Manager supergroups:
    Group that represents managers employed under a given org unit,
    meta-<prefix>-<location-code>.

    Each meta group contains all *manager groups* that are organized under
    this location code in the org tree.  This script creates and deletes
    supergroups and maintains supergroup memberships.

Example
========
Given an org tree with the following location codes (-> indicates
parent-child relationship):
::

                       +-> (stedkode 325000) -+-> (stedkode 325100)
                       |
    (stedkode 320000) -+                      +-> (stedkode 321001)
                       |                      |
                       +-> (stedkode 321000) -+-> (stedkode 321003)

... then this script would typically create the following groups and
memberships (-> indicates group-member relationship):
::

                             +-> (adm-leder-320000)
                             +-> (adm-leder-325000)
    (meta-adm-leder-320000) -+-> (adm-leder-325100)
                             +-> (adm-leder-321000)
                             +-> (adm-leder-321003)
                             +-> (adm-leder-321001)

    (meta-adm-leder-325000) -+-> (adm-leder-325000)
                             +-> (adm-leder-325100)

                             +-> (adm-leder-321000)
    (meta-adm-leder-321000) -+-> (adm-leder-321003)
                             +-> (adm-leder-321001)
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import datetime
import logging

import six

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.group import group_sync
from Cerebrum.modules.no.uio.hr_import import leader_groups as mgr_groups
from Cerebrum.utils import argutils

logger = logging.getLogger(__name__)


def build_id_map(db):
    """ Build an org unit id to location code mapping. """
    ou = Factory.get("OU")(db)
    id_map = {}
    for row in ou.get_stedkoder():
        ou.clear()
        ou.find(row['ou_id'])
        if not ou.get_entity_quarantine(only_active=True):
            id_map[ou.entity_id] = ou.get_stedkode()
    return id_map


def build_org_structure(db, perspective, id_map):
    """
    Build an org tree using given identifiers.

    :param db:
    :param perspective: org tree to use
    :param dict id_map:
        A map of ou_id to alternative ou identifiers.

        The new identifier will be used in the return values.

        Only org units with a mapped identifier will be included in the
        hierarchy.

        Will currently include all children, regardless of ou state
        This means that children of itermediate disabled/quarantined/otherwise
        omitted org units will be included.
    """
    org_tree = {}

    logger.debug("caching org tree...")
    ou = Factory.get("OU")(db)
    for ou_id in id_map:
        org_tree[ou_id] = set(
            child_id
            for child_id in ou.list_children(perspective,
                                             entity_id=ou_id,
                                             recursive=True)
            if child_id in id_map
        )

    for ou_id in sorted(org_tree):
        ident = id_map[ou_id]
        children = [id_map[child_id] for child_id in org_tree[ou_id]]
        yield ident, children


def _get_group_by_id(db, group_id):
    gr = Factory.get("Group")(db)
    gr.find(group_id)
    return gr


def update_manager_groups(db, perspective, id_map):
    """
    Build group hierarchy of manager groups.

    :param perspective: The org tree perspective to use
    :param dict id_map: A set of org units (and their loation codes)
    """
    logger.debug("Building manager group hierarchy...")
    group_structure = dict(build_org_structure(db, perspective, id_map))

    logger.debug("Building current manager groups...")
    # group_cache = manager_groups.ManagerGroupCache(db)

    groups = mgr_groups.ManagerGroups(db)
    supergroups = mgr_groups.ManagerSupergroups(db)

    current_groups = set()
    for parent_ident, children in group_structure.items():
        # Build and sync supergroup and member groups:
        #  - supergroup (e.g. meta-adm-leder-102200)
        #  - member group (e.g. adm-leder-102200)
        #  - org subunit members (e.g. adm-leder-102234, adm-leder-102235, ...)
        supergroup = supergroups.get_group(parent_ident)
        member_ids = set((groups.get_group(parent_ident).entity_id,))
        member_ids.update(groups.get_group(child_ident).entity_id
                          for child_ident in children)

        group_sync.set_group_members(supergroup, member_ids)

        # Include all up-to-date group ids in return value
        current_groups.add(supergroup.entity_id)
        current_groups.update(member_ids)

    return current_groups


def process_manager_groups(db, perspective):
    """
    Build group hierarchy of manager groups.

    :param str prefix: The group name prefix to build groups for
    :param perspective: The org tree perspective to use
    :param dict id_map: A set of org units (and their loation codes)
    """
    logger.debug("Caching org units...")
    id_map = build_id_map(db)
    logger.info("Found %d org units", len(id_map))

    logger.debug("Cache all existing manager groups...")
    initial_groups = mgr_groups.ManagerGroups.list_groups(db)
    initial_groups.update(mgr_groups.ManagerSupergroups.list_groups(db))
    logger.info("Found %d existing manager groups and supergroups",
                len(initial_groups))

    current_groups = update_manager_groups(db, perspective, id_map)
    logger.info("Updated %d current manager groups and supergroups",
                len(current_groups))

    obsolete_groups = initial_groups - current_groups
    expire_groups(db, obsolete_groups)
    logger.info("Removed %d obsolete manager groups and supergroups",
                len(obsolete_groups))


def expire_groups(db, obsolete_groups):
    today = datetime.date.today()
    for group_id in obsolete_groups:
        gr = _get_group_by_id(db, group_id)
        logger.info("Set expire date for obsolete group: %s",
                    gr.group_name)
        gr.expire_date = today
        gr.write_db()


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Update manager groups and group structure",
    )
    perspective_arg = parser.add_argument(
        '--perspective',
        type=six.text_type,
        help="Org tree perspective for manager supergroups (e.g. orgreg-tree)",
        required=True
    )
    argutils.add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf("cronjob", args)

    db = Factory.get('Database')()
    db.cl_init(change_program=parser.prog)
    co = Factory.get('Constants')(db)

    perspective = argutils.get_constant(db, parser, co.OUPerspective,
                                        args.perspective,
                                        argument=perspective_arg)

    process_manager_groups(db, perspective)

    if args.commit:
        logger.info('Committing changes')
        db.commit()
    else:
        logger.info('Rolling back changes')
        db.rollback()
    logger.info('Done with %s', parser.prog)


if __name__ == '__main__':
    main()
