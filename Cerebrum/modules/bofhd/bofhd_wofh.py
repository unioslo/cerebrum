#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
"""This is a bofhd module for commands required by WOFH/brukerinfo."""

from six import text_type

from Cerebrum.group.memberships import GroupMemberships
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.cmd_param import (Command, Id)


class BofhdWOFHExtension(BofhdCommonMethods):

    all_commands = {}
    hidden_commands = {}
    authz = BofhdAuth

    #
    # group all_account_memberships
    #
    hidden_commands['group_all_account_memberships'] = Command(
        ('group', 'all_account_memberships'),
        Id()
    )

    def group_all_account_memberships(self, operator, account_id):
        """
        Hidden command used by brukerinfo/WOFH.

        Returns all groups associated with an account. If a account is the
        primary we add any person groups as if primary account was a member.
        """
        account = self._get_entity('account', account_id)
        account_name = account.get_account_name()
        person = self._get_entity('person', account_name)

        if account.entity_id == person.get_primary_account():
            # Primary account, add person memberships.
            member_id = [account.entity_id, person.entity_id]
        else:
            member_id = account.entity_id
        group_memberships = GroupMemberships(self.db)

        return [
            {'entity_id': row['group_id'],
             'group': row['name'],
             'description': row['description'],
             'expire_date': row['expire_date'],
             'group_type': text_type(self.const.GroupType(row['group_type']))
             }
            for row in group_memberships.get_groups(
                member_id)]
