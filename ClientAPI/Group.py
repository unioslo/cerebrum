# -*- coding: utf-8 -*-
# Copyright 2014 University of Oslo, Norway
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
"""Group client stuff."""


from Cerebrum.Utils import Factory
from Cerebrum import Errors
from ClientAPI.core import ClientAPI
from ClientAPI.core import Utils
from Cerebrum.Group import GroupAPI

from Cerebrum.modules.bofhd.auth import BofhdAuth

# TODO: move this?
from Cerebrum.modules.cis.Utils import commit_handler


class Group(ClientAPI):
    """Exposing API for group functions."""

    def __init__(self, operator_id, service_name, config):
        """Init the API.

        :type operator_id: int
        :param operator_id: The operator ID, used for auth

        :type service_name: string
        :param service_name: The calling service name
        """
        super(Group, self).__init__(service_name)
        self.operator_id = operator_id
        self.config = config

        self.ba = BofhdAuth(self.db)

    @commit_handler()
    def group_create(self, name, description,
                     expire_date=None, visibility='A'):
        """Create a group.

        :type name: string
        :param name: The groups name.

        :type description: string
        :param description: The groups description.

        :type expire_date: DateTime
        :param expire_date: The groups expiration date.

        :type visibility: string
        :param visibility: The groups visibility. Can one of:
            'A'  All
            'I'  Internal
            'N'  None
        """
        # Perform auth-check
        self.ba.can_create_group(self.operator_id, groupname=name)

        # Check if group exists
        if Utils.get_group(self.db, 'name', name):
            raise Errors.CerebrumRPCException('Group already exists.')

        co = Factory.get('Constants')(self.db)
        gr = Factory.get('Group')(self.db)

        # Test if visibility is sane
        vis = co.GroupVisibility(visibility)
        try:
            int(vis)
        except (Errors.NotFoundError, TypeError):
            raise Errors.CerebrumRPCException('Invalid visibility.')

        # Create the group
        # TODO: Moar try/except?
        GroupAPI.group_create(gr, self.operator_id, vis, name,
                              description, expire_date)

        # Set moderator if appropriate.
        # TODO: use the commented version when we pass the config as a dict.
        if getattr(self.config, 'GROUP_OWNER_OPSET', None):
            # Fetch operator.
            en = Utils.get_entity_by_id(self.db, self.operator_id)
            # Grant auth
            GroupAPI.grant_auth(en, gr, getattr(self.config,
                                'GROUP_OWNER_OPSET'))
        return gr.entity_id

    @commit_handler()
    def group_info(self, group_id_type, group_id):
        """Get information about a group.

        :type group_id_type: string
        :param group_id_type: Group identifier type, 'id' or 'group_name'

        :type group_id: string
        :param group_id: Group identifier
        """
        gr = Utils.get(self.db, 'group', group_id_type, group_id)

        # Check if group exists
        if not gr:
            raise Errors.CerebrumRPCException(
                'Group %s:%s does not exist.' % (group_id_type, group_id))

        return GroupAPI.group_info(gr)

    @commit_handler()
    def group_list(self, group_id_type, group_id):
        """Get list of group members

        :type group_id_type: string
        :param group_id_type: Group identifier type, 'id' or 'group_name'

        :type group_id: string
        :param group_id: Group identifier

        :rtype: list(dict{'name': name or id, 'type': type})
        """
        gr = Utils.get(self.db, 'group', group_id_type, group_id)

        # Check if group exists
        if not gr:
            raise Errors.CerebrumRPCException(
                'Group %s:%s does not exist.' % (group_id_type, group_id))

        lst = [{'name': x[1], 'type': x[0]} for x in
               map(Utils.get_entity_designator, GroupAPI.group_list(gr))]
        return lst

    @commit_handler()
    def group_add_member(self, group_id_type, group_id,
                         member_id_type, member_id):
        """Add a member to a group.

        :type group_id_type: string
        :param group_id_type: Group identifier type, 'id' or 'group_name'

        :type group_id: string
        :param group_id: Group identifier

        :type member_id_type: string
        :param member_id_type: Member identifier type, 'id' or 'account_name'

        :type member_id: string
        :param member_id: Member identifier

        :rtype: boolean
        """
        # Get the group
        gr = Utils.get(self.db, 'group', group_id_type, group_id)

        if not gr:
            raise Errors.CerebrumRPCException(
                'Group %s:%s does not exist.' % (group_id_type, group_id))

        # Perform auth check
        self.ba.can_alter_group(self.operator_id, gr)

        # Get the member we want to add
        member = Utils.get(self.db, 'entity', member_id_type, member_id)

        if not member:
            raise Errors.CerebrumRPCException(
                'Entity %s:%s does not exist.' % (member_id_type, member_id))

        if gr.has_member(member.entity_id):
            return False

        GroupAPI.add_member(gr, member.entity_id)
        return True

    @commit_handler()
    def group_remove_member(self, group_id_type, group_id,
                            member_id_type, member_id):
        """Remove a member from a group.

        :type group_id_type: string
        :param group_id_type: Group identifier type, 'id' or 'group_name'

        :type group_id: string
        :param group_id: Group identifier

        :type member_id_type: string
        :param member_id_type: Member identifier type, 'id' or 'account_name'

        :type member_id: string
        :param member_id: Member identifier

        :rtype: boolean
        """
        # Get the group
        gr = Utils.get(self.db, 'group', group_id_type, group_id)

        if not gr:
            raise Errors.CerebrumRPCException(
                'Group %s:%s does not exist.' % (group_id_type, group_id))

        # Perform auth check
        self.ba.can_alter_group(self.operator_id, gr)

        # Get the member we want to add
        member = Utils.get(self.db, 'entity', member_id_type, member_id)

        if not member:
            raise Errors.CerebrumRPCException(
                'Entity %s:%s does not exist.' % (member_id_type, member_id))

        if not gr.has_member(member.entity_id):
            return False

        GroupAPI.remove_member(gr, member.entity_id)
        return True

    @commit_handler()
    def group_set_expire(self, group_id_type, group_id, expire_date=None):
        """Set an expire-date on a group.

        :type group_id_type: str
        :param group_id_type: Group identifier type, 'id' or 'group_name'

        :type group_id: str
        :param group_id: Group identifier

        :type expire_date: <mx.DateTime>
        :param expire_date: The expire-date to set, or None.
        """
        # Get group
        gr = Utils.get(self.db, 'group', group_id_type, group_id)

        if not gr:
            raise Errors.CerebrumRPCException(
                'Group %s:%s does not exist.' % (group_id_type, group_id))

        # Perform auth check
        self.ba.can_alter_group(self.operator_id, gr)

        GroupAPI.set_expire_date(gr, expire_date)
