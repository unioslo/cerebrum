# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

import Cerebrum.Group

from Cerebrum.extlib import sets

import Registry
registry = Registry.get_registry()

Builder = registry.Builder
Attribute = registry.Attribute
Method = registry.Method

CerebrumAttr = registry.CerebrumAttr
CerebrumTypeAttr = registry.CerebrumTypeAttr

Entity = registry.Entity

GroupVisibilityType = registry.GroupVisibilityType
GroupMemberOperationType = registry.GroupMemberOperationType

__all__ = ['Group', 'GroupMember']

class Group(Entity):
    slots = Entity.slots + [CerebrumAttr('name', 'string', 'group_name', write=True),
                            CerebrumAttr('description', 'string', write=True),
                            CerebrumTypeAttr('visibility', 'GroupVisibilityType',
                                             GroupVisibilityType, write=True),
                            CerebrumAttr('expire_date', 'Date', write=True)]
    method_slots = Entity.method_slots + [Method('get_group_members', 'GroupMemberSeq')]

    cerebrum_class = Cerebrum.Group.Group

    def get_group_members(self):
        members = []
        e = Cerebrum.Group.Group(self.get_database())
        e.entity_id = self._entity_id

        union, intersection, difference = e.list_members()

        unionType = GroupMemberOperationType('union')
        intersectionType = GroupMemberOperationType('intersection')
        differenceType = GroupMemberOperationType('difference')

        for rows, operation in ((union, unionType),
                                (intersection, intersectionType),
                                (difference, differenceType)):
            for member_type, member_id in rows:
                member = Entity(int(member_id))
                members.append(GroupMember(group=self,
                                           operation=operation,
                                           member=member))
        return members

class GroupMember(Builder):
    primary = [Attribute('group', 'Group'),
               Attribute('operation', 'GroupMemberOperationType'),
               Attribute('member', 'Entity')]
    slots = primary + []
