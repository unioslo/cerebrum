# coding: utf-8
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
"""This module contains functionality necessary for maintaining automatic
groups reflecting the OU-structure of an organization
"""
from __future__ import unicode_literals
import logging

import cereconf

from Cerebrum import Errors
from Cerebrum.utils.funcwrap import memoize
from Cerebrum.Utils import Factory

logger = logging.getLogger(__name__)

PREFIX_2_DESCRIPTION = {
    'adm-leder-': 'Administrerende leder ved {}',
    'meta-adm-leder-': 'Administrerende ledere ved {} og underenheter',
}


@memoize
def get_initial_account_id(database):
    ac = Factory.get('Account')(database)
    ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    return ac.entity_id


def cache_stedkoder(ou):
    ou_id2sko = {}
    for row in ou.get_stedkoder():
        ou.clear()
        ou.find(row['ou_id'])
        if not ou.is_quarantined():
            ou_id2sko[ou.entity_id] = ou.get_stedkode()
    return ou_id2sko


def get_automatic_group(database, stedkode, prefix):
    """Get or create an automatic group corresponding to ou at 'stedkode'"""
    description = PREFIX_2_DESCRIPTION[prefix]
    name = prefix + stedkode
    gr = Factory.get('Group')(database)
    co = Factory.get('Constants')(database)
    try:
        gr.find_by_name(name)
    except Errors.NotFoundError:
        gr.clear()
        gr.populate(creator_id=get_initial_account_id(database),
                    visibility=co.group_visibility_internal,
                    name=name,
                    description=description.format(stedkode),
                    group_type=co.group_type_affiliation)
        gr.write_db()
    return gr


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
                                     recursive=True,
                                     as_rows=False):
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
    for group_id in wanted_memberships.difference(current_memberships):
        gr.clear()
        gr.find(group_id)
        gr.add_member(entity_id)
    for group_id in current_memberships.difference(wanted_memberships):
        gr.clear()
        gr.find(group_id)
        gr.remove_member(entity_id)
