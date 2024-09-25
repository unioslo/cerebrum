# -*- coding: utf-8 -*-
#
# Copyright 2021-2024 University of Oslo, Norway
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
Sync group membership for a given entity.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

logger = logging.getLogger(__name__)


class GroupMembershipSetter(object):
    """
    Set membership for a single entity in a given group.

    This callable class can be used as a callback for adding an entity to, or
    removing an entity from a predefined group:

    ::

        get_group = Cerebrum.group.template.GroupTemplate('example', 'desc')
        set_membership = GroupMembershipSetter(get_group)
        entity_id = 1
        set_membership(db, entity_id, True)  # add
        set_membership(db, entity_id, False) # remove
    """
    def __init__(self, get_group):
        """
        :param callable get_group:
            A callable that returns the group to update.

            The callback should take a single argument - the database
            connection/transaction to use, and should return the
            Cerebrum.Group.Group object to update.

            Would typically be a :class:`Cerebrum.group.template.GroupTemplate`
            or similar callable object.
        """
        self.get_group = get_group

    def __repr__(self):
        return '<{name} {get_group}>'.format(
            name=type(self).__name__,
            get_group=repr(self.get_group),
        )

    def __call__(self, db, entity_id, set_member):
        """
        Ensure entity_id is or isn't a member of this group.

        :type db: Cerebrum.database.Database
        :param int entity_id: member id to sync
        :param bool set_member: if entity_id should be a member

        :returns bool: True if membership was changed
        """
        group = self.get_group(db)
        is_member = group.has_member(entity_id)

        if set_member and not is_member:
            logger.info('adding entity_id=%d to group %s (%d)',
                        entity_id, group.group_name, group.entity_id)
            group.add_member(entity_id)
            return True

        if not set_member and is_member:
            logger.info('removing entity_id=%d from group %s (%d)',
                        entity_id, group.group_name, group.entity_id)
            group.remove_member(entity_id)
            return True

        return False
