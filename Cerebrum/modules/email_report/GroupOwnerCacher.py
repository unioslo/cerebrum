#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2019 University of Oslo, Norway
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
"""Cache group admins/owners and info about their owned groups"""
from __future__ import unicode_literals
import itertools
import collections

import cereconf

from Cerebrum.utils.funcwrap import memoize

from Cerebrum.Utils import Factory
from Cerebrum.group.GroupRoles import GroupRoles


class GroupOwnerCacher(object):
    def __init__(self, db, manage_link):
        self.db = db
        self.en = Factory.get('Entity')(db)
        self.co = Factory.get('Constants')(db)
        self.person = Factory.get('Person')(db)
        self.group = Factory.get('Group')(db)
        self.account = Factory.get('Account')(db)
        self.manage_link = manage_link

    @memoize
    def get_group_name(self, group_id):
        self.group.clear()
        self.group.find(group_id)
        return self.group.group_name

    def cache_member_id2group_ids(self, group_ids):
        """Maps an entity_id to the group_ids where it is a member

        :type group_ids: list
        :arg group_ids: the group_ids to search for membership
        :returns: a mapping of entity_id to a list of group_ids
        """
        cache = collections.defaultdict(list)
        for group_id in group_ids:
            for member in self.group.search_members(
                    group_id=group_id,
                    member_type=self.co.entity_account):
                cache[member['member_id']].append(group_id)
        return cache

    def cache_owner_id2groups(self, admin_type, fields, nr_of_admins=None):
        """Caches entities which are admins for a group

        :returns: a mapping from owner_id to a list of dicts on the form:
            {
                group_id: unicode,
                group_name: unicode,
                manage_link: unicode
            }
        """
        def get_field_value(field_key, row):
            return field_mapping[field_key](row)

        def get_owner_group_name(row):
            return self.get_group_name(row['admin_id'])

        field_mapping = {
            'group_id': lambda row: row['group_id'],
            'group_name': lambda row: row['group_name'],
            'owner_group_name': get_owner_group_name,
            'manage_link': lambda row: (self.manage_link + row['group_name'])
        }

        owner_id2groups = collections.defaultdict(list)
        roles = GroupRoles(self.db)

        # TODO:
        #   This should help us filter out most personal file groups, but
        #   unfortunately there are still groups which have not been
        #   categorized correctly.
        manual_group_types = list(
            self.co.GroupType(i) for i in
            cereconf.PERISHABLE_MANUAL_GROUP_TYPES
        )

        admins = roles.search_admins(
            admin_type=admin_type,
            group_type=manual_group_types,
            include_group_name=True)

        if nr_of_admins:
            admins = itertools.islice(admins, nr_of_admins)
        for admin in admins:
            owner_id2groups[admin['admin_id']].append({
                field: get_field_value(field, admin) for field in fields
            })
        return owner_id2groups

    def cache_group_id2members(self, groups):
        group_id2members = {}
        for group in groups:
            group_id = group['group_id']
            members_count = len(
                [m for m in self.group.search_members(group_id=group_id)]
            )
            group_id2members[group_id] = members_count
        return group_id2members
