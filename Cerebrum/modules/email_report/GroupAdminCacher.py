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
"""Cache group admins and info about their groups"""
from __future__ import unicode_literals
import datetime
import itertools
import collections

import six

import cereconf

from Cerebrum.utils.funcwrap import memoize

from Cerebrum.Utils import Factory
from Cerebrum.group.GroupRoles import GroupRoles


class GroupAdminCacher(object):
    def __init__(self, db, manage_link, filter_expired=False):
        self.db = db
        self.en = Factory.get('Entity')(db)
        self.co = Factory.get('Constants')(db)
        self.person = Factory.get('Person')(db)
        self.group = Factory.get('Group')(db)
        self.account = Factory.get('Account')(db)
        self.manage_link = manage_link
        self.filter_expired = filter_expired

    @memoize
    def get_group_name(self, group_id):
        self.group.clear()
        self.group.find(group_id)
        return self.group.group_name

    @memoize
    def count_members(self, group_id):
        return len([
            m['member_id'] for m in self.group.search_members(
                group_id=group_id)
        ])

    @memoize
    def count_changes(self, group_id, change_types, days=30):
        """Count changes which has happened to a group

        :type group_id: str
        :param days: start date to count changes from
        :type change_types: tuple
        """
        start_date = datetime.datetime.today() - datetime.timedelta(days=days)
        counts = {}
        for change_type in change_types:
            events = self.db.get_log_events(types=change_type,
                                            sdate=str(start_date),
                                            subject_entity=group_id)
            counts[str(change_type)] = len(list(events))
        return counts

    def include_group(self):
        if self.filter_expired:
            self.group.clear()
            self.group.find(group_id)
            return self.group.is_expired()
        return True

    def cache_member_id2group_ids(self, group_ids, member_type=None):
        """Maps an entity_id to the group_ids where it is a member

        :type member_type: Cerebrum.Constants._EntityTypeCode
        :type group_ids: list
        :arg group_ids: the group_ids to search for membership
        :returns: a mapping of entity_id to a list of group_ids
        """
        if member_type is None:
            member_type = self.co.entity_account
        cache = collections.defaultdict(list)
        for group_id in group_ids:
            if self.include_group(group_id):
                for member in self.group.search_members(
                        group_id=group_id,
                        member_type=member_type):
                    cache[member['member_id']].append(group_id)
        return cache

    def cache_admins_by_membership(self, fields, nr_of_admins=None, **kwargs):
        admin_id2group_info = self.cache_admin_id2group_info(
            self.co.entity_group,
            fields,
            nr_of_admins=nr_of_admins,
            **kwargs
        )
        account_id2admin_ids = self.cache_member_id2group_ids(
            admin_id2group_info.keys())
        account_id2group_info = collections.defaultdict(list)
        for account_id, admin_ids in six.iteritems(account_id2admin_ids):
            for admin_id in admin_ids:
                account_id2group_info[account_id].extend(
                    admin_id2group_info[admin_id])
        return account_id2group_info

    def cache_direct_admins(self, fields, nr_of_admins=None, **kwargs):
        return self.cache_admin_id2group_info(self.co.entity_account,
                                              fields,
                                              nr_of_admins=nr_of_admins,
                                              **kwargs)

    def cache_admin_id2group_info(self, admin_type, fields, nr_of_admins=None,
                                  **kwargs):
        def get_field_value(field_key, *args):
            return field_mapping[field_key](*args)

        field_mapping = {
            'group_id': lambda a_id, g_id: g_id,
            'group_name': lambda a_id, g_id: self.get_group_name(g_id),
            'owner_group_name': lambda a_id, g_id: self.get_group_name(a_id),
            'manage_link': lambda a_id, g_id: (self.manage_link +
                                               self.get_group_name(g_id)),
            'changes': lambda a_id, g_id: (
                self.count_changes(g_id, kwargs['change_types'])),
            'members': lambda a_id, g_id: six.text_type(
                self.count_members(g_id))
        }

        admin_id2group_info = collections.defaultdict(list)

        for admin_id, group_id in self.cache_manual_group_admins(
                admin_type,
                nr_of_admins=nr_of_admins
        ):
            if self.include_group(group_id):
                admin_id2group_info[admin_id].append({
                    field: get_field_value(field, admin_id, group_id)
                    for field in fields
                })
        return admin_id2group_info

    def cache_manual_group_admins(self, admin_type, nr_of_admins=None):
        """Caches admins of manual groups

        :returns: a set of (admin_id, group_id)
        """

        group_admins = set()
        roles = GroupRoles(self.db)

        manual_group_types = tuple(
            self.co.GroupType(i) for i in
            cereconf.PERISHABLE_MANUAL_GROUP_TYPES
        )
        for admin in roles.search_admins(admin_type=admin_type,
                                         group_type=manual_group_types):
            group_admins.add((admin['admin_id'], admin['group_id']))
        if nr_of_admins is not None:
            group_admins = itertools.islice(group_admins,
                                            nr_of_admins)
        return group_admins
