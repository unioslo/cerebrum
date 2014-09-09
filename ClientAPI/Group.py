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

# TODO: Describe the above better.

import cerebrum_path
getattr(cerebrum_path, '', None)  # Silence the linter.
import cereconf

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
        :param operator_id: The operators id, used for auth.

        :type service_name: str
        :param service_name: The calling serices name.
        """
        super(Group, self).__init__(service_name)
        self.operator_id = operator_id
        self.config = config

        self.ba = BofhdAuth(self.db)

    @commit_handler()
    def group_create(self, name, description,
                     expire_date=None, visibility='A'):
        """Create a group.

        :type name: str
        :param name: The groups name.

        :type description: str
        :param description: The groups description.

        :type expire_date: DateTime
        :param expire_date: The groups expiration date.

        :type visibility: str
        :param visibility: The groups visibility. Can one of:
            'A'  All
            'I'  Internal
            'N'  None
        """
        # Perform auth-check
        self.ba.can_create_group(self.operator_id)

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
            en = Utils.get_entity(self.db, self.operator_id)
            # Grant auth
            GroupAPI.grant_auth(en, gr, getattr(self.config,
                                'GROUP_OWNER_OPSET'))
#        if self.config.get('GROUP_OWNER_OPSET', None):
#            GroupAPI.grant_auth(en, gr, self.config.get('GROUP_OWNER_OPSET'))
        return gr.entity_id
