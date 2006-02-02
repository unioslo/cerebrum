# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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

from Cerebrum.extlib import sets

from SpineLib.Builder import Method
from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr

from Entity import Entity
from Group import Group
from Types import EntityType, GroupMemberOperationType, Spread
from Commands import Commands

from SpineLib import Registry
registry = Registry.get_registry()

table = 'group_member'
class GroupMember(DatabaseClass):
    primary = (
        DatabaseAttr('group', table, Group),
        DatabaseAttr('operation', table, GroupMemberOperationType),
        DatabaseAttr('member', table, Entity),
        DatabaseAttr('member_type', table, EntityType)
    )
    db_attr_aliases = {
        table:{
            'group':'group_id',
            'member':'member_id'
        }
    }

registry.register_class(GroupMember)

def get_group_members(self):
    s = registry.GroupMemberSearcher(self.get_database())
    s.set_group(self)
    return s.search()

Group.register_method(Method('get_group_members', [GroupMember]), get_group_members)

UnionType = 'union'
IntersectionType = 'intersection'
DifferenceType = 'difference'

def _get_members(group, group_members):
    unions = sets.Set()
    intersects = sets.Set()
    differences = sets.Set()

    for entity, operation in group_members[group]:
        if entity.get_type().get_name() is Group.entity_type:
            members = _get_members(entity, group_members)
        else:
            members = sets.Set([entity])

        if operation.get_name() == UnionType:
            unions.update(members)
        elif operation.get_name() == IntersectionType:
            intersects.update(members)
        elif operation.get_name() == DifferenceType:
            differences.update(members)

    if intersects:
        unions.intersection_update(intersects)
    if differences:
        unions.difference_update(differences)

    return unions

# FIXME: burde kanskje sjekke for sykler?

def get_groups(self):
    group_members = {}
    def get(entity):
        s = registry.GroupMemberSearcher(self.get_database())
        s.set_member(entity)
        for i in s.search():
            group = i.get_group()
            if group not in group_members:
                group_members[group] = []
            group_members[group].append((entity, i.get_operation()))
            get(group)
    get(self)

    return [i for i in group_members if self in _get_members(i, group_members)]

Entity.register_method(Method('get_groups', [Group]), get_groups)

def get_direct_groups(self):
    groups = sets.Set(get_groups(self))
    searcher = registry.GroupMemberSearcher(self.get_database())
    searcher.set_member(self)
    union = registry.GroupMemberOperationType(self.get_database(), name="union")
    searcher.set_operation(union)
    groups.intersection_update([i.get_group() for i in searcher.search()])
    return list(groups)

Entity.register_method(Method('get_direct_groups', [Group]), get_direct_groups)

def get_members(self):
    """
    Return a flattened list of all entities in this group and its subgroups.
    """

    group_members = {}

    def get(group):
        if group not in group_members:
            group_members[group] = []
        for i in get_group_members(group):
            member = i.get_member()
            group_members[group].append((member, i.get_operation()))

            if member.get_type().get_name() == Group.entity_type:
                get(member)
    get(self)

    members = list(_get_members(self, group_members))
    members.sort(lambda x,y: cmp(x.get_name(), y.get_name()))
    return members


Group.register_method(Method('get_members', [Entity]), get_members)

def add_member(self, entity, operation):
    obj = self._get_cerebrum_obj()
    obj.add_member(entity.get_id(), entity.get_type().get_id(), operation.get_id())
    obj.write_db()

Group.register_method(Method('add_member', None, args=[('entity', Entity), ('operation', GroupMemberOperationType)], write=True), add_member)

def remove_member(self, group_member):
    obj = self._get_cerebrum_obj()
    obj.remove_member(group_member.get_member().get_id(), group_member.get_operation().get_id())
    obj.write_db()

Group.register_method(Method('remove_member', None, args=[('group_member', GroupMember)], write=True), remove_member)

# arch-tag: 62cc34ca-6553-4fcc-bed2-70c0d7dcf6e9
