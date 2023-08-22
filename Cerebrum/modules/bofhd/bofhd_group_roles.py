# -*- coding: utf-8 -*-
#
# Copyright 2023 University of Oslo, Norway
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
This module contains commands for modifying group roles.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging
import textwrap

import six

from Cerebrum.group.GroupRoles import GroupRoles
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.cmd_param import (
    Command,
    FormatSuggestion,
    GroupName,
    Id,
    SimpleString,
    get_format_suggestion_table,
)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.modules.bofhd.utils import BofhdUtils


logger = logging.getLogger(__name__)


class BofhdGroupRoleAuth(BofhdAuth):
    """ Auth for entity extid_* commands.  """

    def can_add_group_admin(self, operator, group=None, query_run_any=False):
        # Check if group admin
        try:
            if self.can_administrate_group(operator=operator,
                                           group=group,
                                           query_run_any=query_run_any):
                return True
        except PermissionDenied:
            pass

        # Check if access through add-admin op-code

        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator=operator,
                operation=self.const.auth_add_group_admin,
            )

        # TODO: Decide if we want to keep special permissions for groups
        #  through opsets
        if self._has_target_permissions(
                operator=operator,
                operation=self.const.auth_add_group_admin,
                target_type=self.const.auth_target_type_group,
                target_id=group.entity_id,
                victim_id=group.entity_id):
            return True

        raise PermissionDenied("Not allowed to add admin to group")

    def can_remove_group_admin(self, operator, group=None,
                               query_run_any=False):
        try:
            return self.can_add_group_admin(operator=operator, group=group,
                                            query_run_any=query_run_any)
        except PermissionDenied:
            raise PermissionDenied("Not allowed to remove admin from group")

    def can_add_group_moderator(self, operator, group=None,
                                query_run_any=False):
        try:
            # "inherit" permissions from can_add_group_admin
            if self.can_add_group_admin(operator=operator, group=group,
                                        query_run_any=query_run_any):
                return True
        except PermissionDenied:
            pass

        # Check if group moderator
        try:
            return self.can_moderate_group(operator=operator, group=group,
                                           query_run_any=query_run_any)
        except PermissionDenied:
            raise PermissionDenied("Not allowed to add moderator to group")

    def can_remove_group_moderator(self, operator, group=None,
                                   query_run_any=False):
        try:
            return self.can_add_group_moderator(operator=operator, group=group,
                                                query_run_any=query_run_any)
        except PermissionDenied:
            raise PermissionDenied(
                "Not allowed to remove moderator from group")

    def can_list_group_roles(self, operator, admin=None, query_run_any=False):
        """
        List moderated groups for a given admin/moderator.
        """
        # Same permissions as 'group_info' - i.e. everybody gets access
        return True

    def can_list_group_owners(self, operator, group=None, query_run_any=False):
        """
        List admins/moderators for a given group.
        """
        # Same permissions as 'group_info' - i.e. everybody gets access
        return True


# TODO: Consider moving/renaming these commands to:
#
# . group_role admin_add <group> <admin>
# . group_role admin_remove <group> <admin>
# . group_role moderator_add <group> <admin>
# . group_role moderator_remove <group> <admin>
#
CMD_HELP = {
    'group': {
        'group_add_admin': "add admin to group",
        'group_remove_admin': "remove admin from group",
        'group_add_moderator': "add moderator to group",
        'group_remove_moderator': "remove moderator from group",
        'group_list_roles': "list group roles given to an admin/moderator",
        'group_list_owners': "list admins/moderators of a given group",
    },
}

CMD_ARGS = {
    'group-role-admin': [
        "group-role-admin",
        "Enter a group admin/moderator",
        textwrap.dedent(
            """
            Enter a admin/moderator group or account to use.

            Lookup formats:

            - <group-name>
            - group:<group-name>
            - account:<account-name>
            """
        ).lstrip(),
    ],
    'group-role-group': [
        "group-role-group",
        "Enter a group to administrate or moderate",
        textwrap.dedent(
            """
            Enter a group to administrate and/or moderate.
            """
        ).lstrip(),
    ],
    'group-role-type': [
        "group-role-type",
        "Group role",
        textwrap.dedent(
            """
            Select a group role.

            Valid group roles are 'admin' and 'moderator'.

            Some commands use this value for filtering - in which case 'any'
            can be used to include both roles.
            """
        ).lstrip(),
    ],
}


class BofhdGroupRoleCommands(BofhdCommandBase):

    all_commands = {}
    authz = BofhdGroupRoleAuth

    @property
    def util(self):
        try:
            return self.__util
        except AttributeError:
            self.__util = BofhdUtils(self.db)
            return self.__util

    def _get_role_member(self, lookup_string):
        """ Look up a group-role-admin value. """
        try:
            # split <type>:<value>
            lookup_type, lookup_value = lookup_string.split(":", 1)
        except ValueError:
            # default to group:<value>
            lookup_type, lookup_value = "group", lookup_string

        if lookup_type == "group":
            admin = self._get_group(lookup_value)
        elif lookup_type == "account":
            admin = self._get_account(lookup_value)
        else:
            raise CerebrumError("Invalid admin lookup type: "
                                + repr(lookup_type))

        return admin

    def _get_name(self, entity):
        """ Get group/account name from entity. """
        if entity.entity_type == self.const.entity_group:
            return entity.group_name
        if entity.entity_type == self.const.entity_account:
            return entity.account_name
        return None

    def _format_response(self, group, candidate, key="role_owner"):
        """ Format a successful admin/moderator change response. """
        assert key != "group"
        group_type = self.const.GroupType(group.group_type)
        cand_type = self.const.EntityType(candidate.entity_type)
        return {
            'group_id': int(group.entity_id),
            'group_name': group.group_name,
            'group_type': six.text_type(group_type),
            key + '_id': int(candidate.entity_id),
            key + '_name': self._get_name(candidate),
            key + '_type': six.text_type(cand_type),
        }

    #
    # group add_admin <admin> <group>
    #
    all_commands['group_add_admin'] = Command(
        ("group", "add_admin"),
        Id(help_ref="group-role-admin"),
        GroupName(help_ref="group-role-group"),
        fs=FormatSuggestion(
            "OK, added %s as admin for %s",
            ("admin_name", "group_name"),
        ),
        perm_filter='can_add_group_admin',
    )

    def group_add_admin(self, operator, lookup, dest_group):
        group = self._get_group(dest_group)
        # TODO: Should we consider the admin object as well?
        self.ba.can_add_group_admin(operator.get_entity_id(), group)

        admin = self._get_role_member(lookup)
        if (admin.entity_type == self.const.entity_group
                and admin.group_type == self.const.group_type_personal):
            raise CerebrumError(
                "%s (%d) cannot be admin since it is a personal file group"
                % (admin.group_name, admin.entity_id))

        roles = GroupRoles(self.db)
        if roles.is_admin(admin_id=int(admin.entity_id),
                          group_id=int(group.entity_id)):
            raise CerebrumError(
                "%s (%d) is already admin for %s (%d)"
                % (self._get_name(admin), admin.entity_id,
                   group.group_name, group.entity_id))

        # TODO: It makes no sense having both admin and moderator roles.
        # Should we simply *promote an existing moderator role to admin if
        # already moderator?

        roles.add_admin_to_group(int(admin.entity_id), int(group.entity_id))
        return self._format_response(group, admin, key="admin")

    #
    # group remove_admin <admin> <group>
    #
    all_commands['group_remove_admin'] = Command(
        ("group", "remove_admin"),
        Id(help_ref="group-role-admin"),
        GroupName(help_ref="group-role-group"),
        fs=FormatSuggestion(
            "OK, removed %s as admin for %s",
            ("admin_name", "group_name"),
        ),
        perm_filter='can_remove_group_admin',
    )

    def group_remove_admin(self, operator, lookup, dest_group):
        group = self._get_group(dest_group)
        # TODO: Should we consider the admin object as well?
        self.ba.can_remove_group_admin(operator.get_entity_id(), group)

        admin = self._get_role_member(lookup)
        roles = GroupRoles(self.db)
        if not roles.is_admin(admin_id=int(admin.entity_id),
                              group_id=int(group.entity_id)):
            raise CerebrumError(
                "%s (%d) is not admin for %s (%d)"
                % (self._get_name(admin), admin.entity_id,
                   group.group_name, group.entity_id))
        roles.remove_admin_from_group(int(admin.entity_id),
                                      int(group.entity_id))
        return self._format_response(group, admin, key="admin")

    #
    # group add_moderator <moderator> <group>
    #
    all_commands['group_add_moderator'] = Command(
        ("group", "add_moderator"),
        Id(help_ref="group-role-admin"),
        GroupName(help_ref="group-role-group"),
        fs=FormatSuggestion(
            "OK, added %s as moderator for %s",
            ("moderator_name", "group_name"),
        ),
        perm_filter='can_add_group_moderator',
    )

    def group_add_moderator(self, operator, lookup, dest_group):
        group = self._get_group(dest_group)
        # TODO: Should we consider the moderator object as well?
        self.ba.can_add_group_moderator(operator.get_entity_id(), group)

        mod = self._get_role_member(lookup)
        if (mod.entity_type == self.const.entity_group
                and mod.group_type == self.const.group_type_personal):
            raise CerebrumError(
                "%s (%d) cannot be moderator since it is a personal file group"
                % (mod.group_name, mod.entity_id))

        # TODO: It makes no sense having both admin and moderator roles.
        # Should we error out if mod is already an admin?

        roles = GroupRoles(self.db)
        if roles.is_moderator(moderator_id=int(mod.entity_id),
                              group_id=int(group.entity_id)):
            raise CerebrumError(
                "%s (%d) is already moderator for %s (%d)"
                % (self._get_name(mod), mod.entity_id,
                   group.group_name, group.entity_id))
        roles.add_moderator_to_group(int(mod.entity_id), int(group.entity_id))
        return self._format_response(group, mod, key="moderator")

    #
    # group remove_moderator <moderator> <group>
    #
    all_commands['group_remove_moderator'] = Command(
        ("group", "remove_moderator"),
        Id(help_ref="group-role-admin"),
        GroupName(help_ref="group-role-group"),
        fs=FormatSuggestion(
            "OK, removed %s as moderator for %s",
            ("moderator_name", "group_name"),
        ),
        perm_filter='can_remove_group_moderator',
    )

    def group_remove_moderator(self, operator, lookup, dest_group):
        group = self._get_group(dest_group)
        # TODO: Should we consider the moderator object as well?
        self.ba.can_remove_group_moderator(operator.get_entity_id(), group)

        mod = self._get_role_member(lookup)
        roles = GroupRoles(self.db)
        if not roles.is_moderator(moderator_id=int(mod.entity_id),
                                  group_id=int(group.entity_id)):
            raise CerebrumError(
                "%s (%d) is not moderator for %s (%d)"
                % (self._get_name(mod), mod.entity_id,
                   group.group_name, group.entity_id))
        roles.remove_moderator_from_group(int(mod.entity_id),
                                          int(group.entity_id))
        return self._format_response(group, mod, key="moderator")

    #
    # group list_roles <admin/moderator> [role-type]
    #
    all_commands['group_list_roles'] = Command(
        ("group", "list_roles"),
        Id(help_ref="group-role-admin"),
        SimpleString(help_ref="group-role-type", default="any", optional=True),
        fs=get_format_suggestion_table(
            ("role", "Owner Role", 10, "s", True),
            ("group_id", "Group Id", 9, "d", False),
            ("group_name", "Group Name", 20, "s", True),
            limit_key="limit",
        ),
        perm_filter="can_list_group_roles",
    )

    # Any given admin/moderator will probably not have *too* many direct
    # ownerships.  Let's limit the number of results.
    group_list_roles_limit = 100

    def group_list_roles(self, operator, lookup, role="any"):
        mod = self._get_role_member(lookup)
        self.ba.can_list_group_roles(operator.get_entity_id(), mod)
        if role not in ("admin", "moderator", "any"):
            raise CerebrumError("Invalid role type: " + repr(role))

        # Owner is the same value for each entry - let's make this a bit more
        # efficient by only looking it up once...
        owner_name = self._get_entity_name(
            mod.entity_id, self.const.EntityType(mod.entity_type))

        results = []
        for owner in self._search_ownership(owner_id=mod.entity_id,
                                            role=role,
                                            include_owner_name=False):
            if len(results) >= self.group_list_roles_limit:
                # We've found group_list_roles_limit + 1 results; add sentinel
                # to communicate that there *are* more results and stop
                results.append({'limit': self.group_list_roles_limit})
                break
            owner['owner_name'] = owner_name
            results.append(owner)

        if not results:
            raise CerebrumError(
                "Entity %s (type=%s, id=%s) has no group roles"
                % (owner_name,
                   six.text_type(self.const.EntityType(mod.entity_type)),
                   mod.entity_id))
        results.sort(key=lambda r: (r['role'], r['group_name']))
        return results

    #
    # group list_owners <admin/moderator> [role-type]
    #
    all_commands['group_list_owners'] = Command(
        ("group", "list_owners"),
        Id(help_ref="group-role-group"),
        SimpleString(help_ref="group-role-type", default="any", optional=True),
        fs=get_format_suggestion_table(
            ("role", "Owner Role", 10, "s", True),
            ("owner_type", "Owner Type", 10, "s", True),
            ("owner_id", "Owner Id", 9, "d", False),
            ("owner_name", "Owner Name", 20, "s", True),
            limit_key="limit",
        ),
        perm_filter="can_list_group_owners",
    )

    # Any given group will have far fewer admins/moderators.
    group_list_owners_limit = 100

    def group_list_owners(self, operator, target, role="any"):
        group = self._get_group(target)
        self.ba.can_list_group_owners(operator.get_entity_id(), group)
        if role not in ("admin", "moderator", "any"):
            raise CerebrumError("Invalid role type: " + repr(role))

        results = []
        for owner in self._search_ownership(group_id=group.entity_id,
                                            role=role,
                                            include_owner_name=True):
            if len(results) >= self.group_list_owners_limit:
                # We have group_list_owners_limit + 1 results; add sentinel and
                # stop
                results.append({'limit': self.group_list_owners_limit})
                break
            results.append(owner)

        if not results:
            raise CerebrumError("Group %s (%s) has no admins/moderators"
                                % (group.group_name, group.entity_id))

        results.sort(key=lambda r: (r['role'], r['owner_id']))
        return results

    def _search_ownership(self, group_id=None, owner_id=None,
                          role="any", include_owner_name=False):
        """
        List owners (admin and/or moderator) of group(s).

        :param group_id: Filter by owned/moderated group
        :param owner_id: Filter by owner/moderator
        :param role: admin, moderator, or any
        """
        roles = GroupRoles(self.db)

        def _prep_row(row, role):
            owner_id = row[role + '_id']
            owner_type = self.const.EntityType(row[role + '_type'])
            owner = {
                'owner_id': owner_id,
                'owner_type': six.text_type(owner_type),
                'role': role,
                'group_id': row['group_id'],
                'group_name': row['group_name'],
            }
            if include_owner_name:
                owner['owner_name'] = self._get_entity_name(owner_id,
                                                            owner_type)
            return owner

        if role in ("any", "admin"):
            for row in roles.search_admins(admin_id=owner_id,
                                           group_id=group_id,
                                           include_group_name=True):
                yield _prep_row(row, "admin")

        if role in ("any", "moderator"):
            for row in roles.search_moderators(moderator_id=owner_id,
                                               group_id=group_id,
                                               include_group_name=True):
                yield _prep_row(row, "moderator")

    @classmethod
    def get_help_strings(cls):
        """Get help strings."""
        return merge_help_strings(
            get_help_strings(),
            ({}, CMD_HELP, CMD_ARGS),
        )
