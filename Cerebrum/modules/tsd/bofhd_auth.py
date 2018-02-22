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
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied


class TSDBofhdAuth(BofhdAuth):
    """The BofhdAuth class for TSD."""

    def can_generate_otpkey(self, operator, account, query_run_any=False):
        """If the operator is allowed to generate a new OTP key for a given
        account."""
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return False
        # TODO: give the user itself access to regenerate the OTP key
        raise PermissionDenied('Only superusers could regenerate OTP keys')

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
            except:
                raise CerebrumError('Destination group is not a project '
                                    'group.')
            ou = Factory.get('OU')(self._db)
            ou.find(proj_id)
            proj_name = ou.get_project_name()
            if member_type in ("group", self.const.entity_group):
                try:
                    group_trait = src_entity.get_trait('project_group')
                except:
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
