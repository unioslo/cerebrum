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

from GroBuilder import GroBuilder
from Builder import Attribute, Method
from Searchable import Searchable
from CerebrumClass import CerebrumAttr, CerebrumTypeAttr, CerebrumDateAttr


import Registry
registry = Registry.get_registry()

Entity = registry.Entity

GroupVisibilityType = registry.GroupVisibilityType
GroupMemberOperationType = registry.GroupMemberOperationType

__all__ = ['Group', 'GroupMember']

class Group(Entity):
    slots = Entity.slots + [
        CerebrumAttr('name', 'string', 'group_name', write=True),
        CerebrumAttr('description', 'string', write=True),
        CerebrumTypeAttr('visibility', 'GroupVisibilityType', GroupVisibilityType, write=True),
        CerebrumDateAttr('expire_date', 'Date', write=True)]
    method_slots = Entity.method_slots + [
        Method('get_members', 'GroupMemberSeq')]

    cerebrum_class = Cerebrum.Group.Group

    def get_members(self):
        searcher = registry.GroupMemberSearch(self)
        searcher.set_group(self)
        searcher.set_include_subgroups(True)
        return searcher.search()

class GroupMember(GroBuilder, Searchable):
    primary = [
        Attribute('group', 'Group'),
        Attribute('operation', 'GroupMemberOperationType'),
        Attribute('member', 'Entity')]
    slots = primary + []
    search_slots = [
        Attribute('member_type', 'EntityType'),
        Attribute('group_tags', 'SpreadSeq'),
        Attribute('member_tags', 'SpreadSeq'),
        Attribute('include_subgroups', 'boolean'),
        Attribute('include_parentgroups', 'boolean')]

    def create_search_method(cls):
        def search(self, group=None, operation=None, member=None, member_type=None, group_tags=None,
                   member_tags=None, include_subgroups=None, include_parentgroups=None, ignore=()):
            where = []
            args = {}
            if group is not None:
                where.append('group_id = :group_id')
                args['group_id'] = group.get_entity_id()
            if operation is not None:
                where.append('operation = :operation')
                args['operation'] = operation.get_id()
            if member is not None:
                where.append('member_id = :member_id')
                args['member_id'] = member.get_entity_id()
            if member_type is not None:
                where.append('member_type = :member_type')
                args['member_type'] = member_type.get_id()

            # FIXME: legge til støtte for group_tags og member_tags

            db = self.get_database()

            if where:
                where = 'WHERE %s' % ' AND '.join(where)
            else:
                where = ''

            group_members = sets.Set()

            for row in db.query("""SELECT group_id, operation, member_id, member_type
                                   FROM [:table schema=cerebrum name=group_member]
                                   %s""" % where, args):
                group = Group(int(row['group_id']))
                member_operation = GroupMemberOperationType(id=int(row['operation']))
                new_member = Entity(int(row['member_id']),
                                    registry.EntityType(id=int(row['member_type'])))

                group_member = GroupMember(group, member_operation, new_member)

                if group_member not in ignore:
                    group_members.add(group_member)

                    group_type = registry.EntityType('group')

                    if include_subgroups and new_member.get_entity_type() == group_type:
                        group_members.update(search(self, group=new_member, operation=operation,
                            member_type=member_type, include_subgroups=include_subgroups,
                            include_parentgroups=include_parentgroups, ignore=group_members))
                    if include_parentgroups:
                        group_members.update(search(self, member=group, operation=operation,
                            member_type=group_type, include_subgroups=include_subgroups,
                            include_parentgroups=include_parentgroups, ignore=group_members))

            return list(group_members)
        return search
    create_search_method = classmethod(create_search_method)

# arch-tag: e485b7a1-290b-467a-a746-761c30b71e13
