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

from Builder import Method
from DatabaseClass import DatabaseClass, DatabaseAttr

from Entity import Entity
from Group import Group
from Types import EntityType, GroupMemberOperationType

import Registry
registry = Registry.get_registry()

class GroupMember(DatabaseClass):
    primary = [
        DatabaseAttr('group', 'group_member', Group, dbattr_name='group_id'),
        DatabaseAttr('operation', 'group_member', GroupMemberOperationType),
        DatabaseAttr('member', 'group_member', Entity, dbattr_name='member_id'),
        DatabaseAttr('member_type', 'group_member', EntityType)
    ]
    slots = []

registry.register_class(GroupMember)

def get_groups(self):
    s = registry.GroupMemberSearch(self)
    s.set_member(self)
    return s.search()


def get_members(self):
    s = registry.GroupMemberSearch(self)
    s.set_group(self)
    return s.search()

Entity.register_method(Method('get_groups', GroupMember, sequence=True), get_members)
Group.register_method(Method('get_members', GroupMember, sequence=True), get_members)

