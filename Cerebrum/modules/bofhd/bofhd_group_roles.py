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

    @classmethod
    def get_help_strings(cls):
        """Get help strings."""
        return merge_help_strings(
            get_help_strings(),
            ({}, CMD_HELP, CMD_ARGS),
        )
