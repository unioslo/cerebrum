# -*- coding: utf-8 -*-
#
# Copyright 2013-2018 University of Oslo, Norway
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
"""The access control in TSD.

In TSD, you have the user groups:

- superusers: The system administrators.

- Project Administrators (PA): Those who could administrate their own project.

- Project Members (PM): Those who are only members of a project. Should only
  be able to modify some of their own information.

"""
from Cerebrum import Constants
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.utils import _AuthRoleOpCode


class TSDBofhdAuthConstants(Constants.Constants):
    auth_project_create = _AuthRoleOpCode(
        'project_create', 'Create projects')
    auth_project_setup = _AuthRoleOpCode(
        'project_setup', 'Setup projects')
    auth_project_terminate = _AuthRoleOpCode(
        'project_terminate', 'Terminate projects')
    auth_project_approve = _AuthRoleOpCode(
        'project_approve', 'Approve projects')
    auth_project_reject = _AuthRoleOpCode(
        'project_reject', 'Reject projects')
    auth_project_set_end_date = _AuthRoleOpCode(
        'project_set_end_date', 'Set end date for projects')
    auth_project_set_name = _AuthRoleOpCode(
        'project_set_name', 'Set project names')
    auth_project_set_price = _AuthRoleOpCode(
        'project_set_price', 'Set project price')
    auth_project_set_institution = _AuthRoleOpCode(
        'project_set_institution', 'Set project institution')
    auth_project_set_hpc = _AuthRoleOpCode(
        'project_set_hpc', 'Set project HPC')
    auth_project_set_vm_type = _AuthRoleOpCode(
        'project_set_vm_type', 'Set project VM type')
    auth_project_set_project_metadata = _AuthRoleOpCode(
        'project_set_project_metadata', 'Set project metadata')
    auth_project_freeze = _AuthRoleOpCode(
        'project_freeze', 'Freeze projects')
    auth_project_unfreeze = _AuthRoleOpCode(
        'project_unfreeze', 'Unfreeze projects')
    auth_project_list = _AuthRoleOpCode(
        'project_list', 'List projects')
    auth_project_view_info = _AuthRoleOpCode(
        'project_view_info', 'View project information')
    auth_project_affiliate_with_entity = _AuthRoleOpCode(
        'project_affiliate_with_entity', 'Affiliate entity with project')
    auth_project_list_hosts = _AuthRoleOpCode(
        'project_list_hosts', 'List hosts associated with project')
    auth_user_approve = _AuthRoleOpCode(
        'user_approve', 'Approve users')
    auth_user_generate_otp_key = _AuthRoleOpCode(
        'user_generate_otp_key', 'Generate OTP keys for users')
    auth_subnet_view = _AuthRoleOpCode(
        'subnet_view', 'View subnets')


class TSDBofhdAuth(BofhdAuth):
    """The BofhdAuth class for TSD."""

    def can_create_project(self, operator, query_run_any=False):
        """If the operator is allowed to create new projects."""
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(
                operator, self.const.auth_project_create):
            return True
        if query_run_any:
            return False
        raise PermissionDenied('Not authorized to create projects')

    def can_setup_project(self, operator, query_run_any=False):
        """If the operator is allowed to run the setup procedure for
        projects."""
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(
                operator, self.const.auth_project_setup):
            return True
        if query_run_any:
            return False
        raise PermissionDenied('Not authorized to setup projects')

    def can_terminate_project(self, operator, query_run_any=False):
        """If the operator is allowed to terminate projects."""
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(
                operator, self.const.auth_project_terminate):
            return True
        if query_run_any:
            return False
        raise PermissionDenied('Not authorized to terminate projects')

    def can_approve_project(self, operator, query_run_any=False):
        """If the operator is allowed to approve projects."""
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(
                operator, self.const.auth_project_approve):
            return True
        if query_run_any:
            return False
        raise PermissionDenied('Not authorized to approve projects')

    def can_reject_project(self, operator, query_run_any=False):
        """If the operator is allowed to reject projects."""
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(
                operator, self.const.auth_project_reject):
            return True
        if query_run_any:
            return False
        raise PermissionDenied('Not authorized to reject projects')

    def can_freeze_project(self, operator, query_run_any=False):
        """If the operator is allowed to freeze projects."""
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(
                operator, self.const.auth_project_freeze):
            return True
        if query_run_any:
            return False
        raise PermissionDenied('Not authorized to freeze projects')

    def can_unfreeze_project(self, operator, query_run_any=False):
        """If the operator is allowed to unfreeze projects."""
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(
                operator, self.const.auth_project_unfreeze):
            return True
        if query_run_any:
            return False
        raise PermissionDenied('Not authorized to unfreeze projects')

    def can_list_projects(self, operator, query_run_any=False):
        """If the operator is allowed to list projects."""
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(
                operator, self.const.auth_project_list):
            return True
        if query_run_any:
            return False
        raise PermissionDenied('Not authorized to list projects')

    def can_view_project_info(self, operator, query_run_any=False):
        """If the operator is allowed to see information about projects."""
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(
                operator, self.const.auth_project_view_info):
            return True
        if query_run_any:
            return False
        raise PermissionDenied(
            'Not authorized to view information about projects')

    def can_affiliate_entity_with_project(self, operator, query_run_any=False):
        """If the operator is allowed to affiliate entities with projects."""
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(
                operator, self.const.auth_project_affiliate_with_entity):
            return True
        if query_run_any:
            return False
        raise PermissionDenied(
            'Not authorized to view affiliate entity with project')

    def can_set_project_end_date(self, operator, query_run_any=False):
        """If the operator is allowed to set the end date for projects."""
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(
                operator, self.const.auth_project_set_end_date):
            return True
        if query_run_any:
            return False
        raise PermissionDenied('Not authorized to set end date for projects')

    def can_set_project_name(self, operator, query_run_any=False):
        """If the operator is allowed to set names for projects."""
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(
                operator, self.const.auth_project_set_name):
            return True
        if query_run_any:
            return False
        raise PermissionDenied('Not authorized to set names for projects')

    def can_set_project_price(self, operator, query_run_any=False):
        """If the operator is allowed to set price for projects."""
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(
                operator, self.const.auth_project_set_price):
            return True
        if query_run_any:
            return False
        raise PermissionDenied('Not authorized to set price for projects')

    def can_set_project_institution(self, operator, query_run_any=False):
        """If the operator is allowed to set institution for projects."""
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(
                operator, self.const.auth_project_set_institution):
            return True
        if query_run_any:
            return False
        raise PermissionDenied(
            'Not authorized to set institution for projects')

    def can_set_project_hpc(self, operator, query_run_any=False):
        """If the operator is allowed to set HPC for projects."""
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(
                operator, self.const.auth_project_set_hpc):
            return True
        if query_run_any:
            return False
        raise PermissionDenied('Not authorized to set HPC for projects')

    def can_set_project_metadata(self, operator, query_run_any=False):
        """If the operator is allowed to set metadata for projects."""
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(
                operator, self.const.auth_project_set_metadata):
            return True
        if query_run_any:
            return False
        raise PermissionDenied('Not authorized to set metadata for projects')

    def can_set_project_vm_type(self, operator, query_run_any=False):
        """If the operator is allowed to set VM type for projects."""
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(
                operator, self.const.auth_project_set_vm_type):
            return True
        if query_run_any:
            return False
        raise PermissionDenied('Not authorized to set VM type for projects')

    def can_list_project_hosts(self, operator, query_run_any=False):
        """If the operator is allowed to list hosts associated with
        projects."""
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(
                operator, self.const.auth_project_list_hosts):
            return True
        if query_run_any:
            return False
        raise PermissionDenied(
            'Not authorized to list hosts associated with projects')

    def can_view_subnets(self, operator, query_run_any=False):
        """If the operator is allowed to view subnets."""
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(
                operator, self.const.auth_subnet_view):
            return True
        if query_run_any:
            return False
        raise PermissionDenied('Not authorized to view subnets')

    def can_approve_user(self, operator, query_run_any=False):
        """If the operator is allowed to approve users."""
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(
                operator, self.const.auth_user_approve):
            return True
        if query_run_any:
            return False
        raise PermissionDenied('Not authorized to approve users')

    def can_generate_otp_key(self, operator, account, query_run_any=False):
        """If the operator is allowed to generate a new OTP key for a given
        account."""
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(
                operator, self.const.auth_generate_otp_key):
            return True
        if query_run_any:
            return False
        # TODO: give the user itself access to regenerate the OTP key
        raise PermissionDenied('Not authorized to generate OTP keys')

    def can_add_group_member(self, op_id, src_entity, member_type, dest_group):
        """
        Checks if the operator has permission to add group members for
        the given group. TSD requires that members being added by group
        moderators, must be affiliated with the same project as the group
        they're being added to.

        @type op_id: int
        @param op_id: The entity_id of the user performing the operation.

        @type dest_group: EntityType Group
        @param dest_group: The group to add/remove members to/from.
        """

        self.can_alter_group(op_id, dest_group)

        # If not a superuser, ensure that dest_group is a project group,
        # and that src_entity is affiliated with the same project as
        # dest_group.
        if not self.is_superuser(op_id):
            try:
                proj_id = dest_group.get_trait('project_group')['target_id']
            except Exception:
                raise CerebrumError('Destination group is not a project '
                                    'group.')
            ou = Factory.get('OU')(self._db)
            ou.find(proj_id)
            proj_name = ou.get_project_name()
            if member_type in ("group", self.const.entity_group):
                try:
                    group_trait = src_entity.get_trait('project_group')
                except Exception:
                    raise PermissionDenied(
                        'Group to be added is not a project group.')
                if not group_trait['target_id'] == proj_id:
                    raise PermissionDenied(
                        'Group %s is not affiliated with %s'
                        % (src_entity.group_name, proj_name))
            elif member_type in ("account", self.const.entity_account):
                if not src_entity.get_tsd_project_id() == proj_id:
                    raise PermissionDenied(
                        'Account %s is not affiliated with %s.'
                        % (src_entity.account_name, proj_name))
        return True
