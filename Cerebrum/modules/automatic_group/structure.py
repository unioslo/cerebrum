# coding: utf-8
#
# Copyright 2020-2023 University of Oslo, Norway
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
Functionality for building group hierarchies based on org trees.

TODO: This module needs revision.  It was built for- and only used for *manager
groups* (see Cerebrum.modules.no.uio.leader_groups).  Parts of this module
should be moved there.

TODO: This sub-module should probably be named something like
`Cerebrum.modules.org_groups`, to better reflect what it actually *does*.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

from Cerebrum.group.template import GroupTemplate


logger = logging.getLogger(__name__)


PREFIX_2_DESCRIPTION = {
    'adm-leder-': 'Administrerende leder ved {}',
    'meta-adm-leder-': 'Administrerende ledere ved {} og underenheter',
}


def cache_stedkoder(ou):
    ou_id2sko = {}
    for row in ou.get_stedkoder():
        ou.clear()
        ou.find(row['ou_id'])
        if not ou.get_entity_quarantine(only_active=True):
            ou_id2sko[ou.entity_id] = ou.get_stedkode()
    return ou_id2sko


def get_automatic_group(database, stedkode, prefix):
    """Get or create an automatic group corresponding to ou at 'stedkode'"""
    group_name = prefix + stedkode
    group_description = PREFIX_2_DESCRIPTION[prefix].format(stedkode)

    template = GroupTemplate(
        group_name=group_name,
        group_description=group_description,
        # TODO: leader groups should have their own type?
        group_type="affiliation-group",
        # TODO: Visibility "I" - seems wrong
        group_visibility="I",
        conflict=GroupTemplate.CONFLICT_UPDATE,
    )
    return template(database)


def get_current_members(gr, group_id):
    return (r['member_id'] for r in gr.search_members(group_id=group_id,
                                                      indirect_members=False))


def get_automatic_group_ids(gr, co, prefix):
    return (r['group_id'] for r in gr.search(
        name=prefix + '*',
        group_type=co.group_type_affiliation,
        filter_expired=True,
        fetchall=False
    ))


def meta_group_members(db, ou, ou_id, perspective, prefix, ou_id2sko):
    """Get the needed members of meta group at ou 'ou_id' based on OU-structure

    :type db: Cerebrum.CLDatabase.CLDatabase
    :type ou: Cerebrum.Utils._dynamic_OU
    :param ou_id: ou to get members for
    :type perspective: Cerebrum.Constants._OUPerspectiveCode
    :param prefix: prefix of groups to get
    :param ou_id2sko: cache for looking up stedkode of an ou

    """
    yield get_automatic_group(db, ou_id2sko[ou_id], prefix).entity_id
    for child_id in ou.list_children(perspective,
                                     entity_id=ou_id,
                                     recursive=True):
        # It is worth mentioning that OU.list_children() includes child OUs
        # whether they are quarantined or not. We do not want to generate
        # groups at OUs which are quarantined, and the following if-check
        # should filter those out. But what if we encounter a non-quarantined
        # child OU of a quarantined OU? The child OU would get a group
        # generated for it! Is this the preferred behaviour?
        if child_id in ou_id2sko:
            yield get_automatic_group(db,
                                      ou_id2sko[child_id],
                                      prefix).entity_id


def update_members(gr, group_id, current_members, wanted_members):
    """Make sure only the wanted members are in group 'group_id'"""
    gr.clear()
    gr.find(group_id)
    for member_id in wanted_members.difference(current_members):
        gr.add_member(member_id)
    for member_id in current_members.difference(wanted_members):
        gr.remove_member(member_id)


def update_memberships(gr, entity_id, current_memberships, wanted_memberships):
    """Make sure entity 'entity_id' is member of groups 'wanted_membeships'

    This method differentiates the current and wanted memberships of an entity
    and makes the necessary updates to the entity's memberships.

    :type gr: Cerebrum.Utils._dynamic_Group
    :param entity_id: entity to add
    :type current_memberships: set
    :type wanted_memberships: set
    """
    to_add = set(wanted_memberships) - set(current_memberships)
    to_remove = set(current_memberships) - set(wanted_memberships)
    for group_id in to_add:
        gr.clear()
        gr.find(group_id)
        # If we blindly trust the current_memberships input, we may run into
        # problems.  Often, the search for current memberships will *omit
        # expired groups*, and the wanted_memberships *includes* expired
        # groups.
        if not gr.has_member(entity_id):
            gr.add_member(entity_id)
    for group_id in to_remove:
        gr.clear()
        gr.find(group_id)
        if gr.has_member(entity_id):
            gr.remove_member(entity_id)
