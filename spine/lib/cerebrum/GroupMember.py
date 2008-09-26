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
import Cerebrum.Database

from Cerebrum.Utils import Factory
co = Factory.get('Constants')()

from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr
from SpineLib import SpineExceptions

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
    return [i.get_member() for i in s.search()]
get_group_members.signature = [Entity]

def get_groups(self):
    """
    Returns the list of all groups this entity is a member of
    (directly or indirectly).
    """
    groups = []
    def get(entity):
        s = registry.GroupMemberSearcher(self.get_database())
        s.set_member(entity)
        for i in s.search():
            group = i.get_group()
            if group not in groups:
                groups.append(group)
                get(group)
    get(self)

    return groups
get_groups.signature = [Group]

def get_direct_groups(self):
    """Returns the list of groups this entity is a direct member of."""
    searcher = registry.GroupMemberSearcher(self.get_database())
    searcher.set_member(self)
    return [i.get_group() for i in searcher.search()]
get_direct_groups.signature = [Group]

def get_members(self):
    """
    Return a flattened list of all members of this group and its subgroups.
    """
    members = []
    grouptype = EntityType(self.get_database(), int(co.entity_group))
    
    def get(group):
        s = registry.GroupMemberSearcher(self.get_database())
        s.set_group(group)
        
        for groupmember in s.search():
            member=groupmember.get_member()
            membertype=groupmember.get_member_type()
            if member not in members:
                members.append(member)
                #if membertype == grouptype:
                get(member)
    get(self)

    return members
get_members.signature = [Entity]

def add_member(self, entity):
    obj = self._get_cerebrum_obj()

    obj.add_member(entity.get_id())
    obj.write_db()
add_member.signature = None
add_member.signature_args=[Entity]
add_member.signature_write=True
add_member.signature_exceptions = [SpineExceptions.AlreadyExistsError]

def remove_member(self, entity):
    obj = self._get_cerebrum_obj()
    obj.remove_member(entity.get_id())
    obj.write_db()
remove_member.signature = None
remove_member.signature_args=[Entity]
remove_member.signature_write=True

Entity.register_methods([get_groups, get_direct_groups])
Group.register_methods([get_group_members, get_members, add_member, remove_member])
# arch-tag: 62cc34ca-6553-4fcc-bed2-70c0d7dcf6e9
