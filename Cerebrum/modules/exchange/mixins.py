#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015 University of Oslo, Norway
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
"""Base functionality for Exchange objects.

The exchange.mixins module contains mixins that should go into the base
Group classes to support detection, deletion and cleanup of exchange data.

"""
from Cerebrum import Errors
from Cerebrum.Group import Group


class SecurityGroupMixin(Group):
    """ Base functionality for Exchange Security Groups.

    This class is intended as a mixin to the base Group class, to enable
    identification and cleanup of Security Group data.
    """


class DistributionGroupMixin(Group):
    """ Base functionality for Exchange Distribution Groups.

    This class is intended as a mixin to the base Group class, to enable
    identification and cleanup of Distribution Group data.
    """

    def _is_roomlist(self):
        """ Fetch distribution group roomlist flag, if it exists.

        This method can be used to check if a group is a Distribution Group,
        and if so, is it a room list.

        :rtype: basestring
        :return:
            'T' If the DistributionGroup is a roomlist, 'F' if it's not.

        :raise NotFoundError: If the group is not a DistributionGroup.

        """
        return self.query_1("""
        SELECT roomlist
        FROM [:table schema=cerebrum name=distribution_group]
        WHERE group_id=:g_id""", {'g_id': self.entity_id})

    def demote(self):
        """ Remove all subclass-related data for the group. """
        res = self.demote_distribution()
        return super(DistributionGroupMixin, self).demote() or res

    def demote_distribution(self):
        """ Remove all exchange-related data for the group. """
        is_roomlist = None
        try:
            is_roomlist = self._is_roomlist()
        except Errors.NotFoundError:
            return False
        binds = {'g_id': self.entity_id}
        exists_stmt = """
          SELECT EXISTS (
            SELECT 1
            FROM [:table schema=cerebrum name=distribution_group]
            WHERE group_id=:g_id
          )
        """
        if self.query_1(exists_stmt, binds):
            # True positive
            delete_stmt = """
            DELETE FROM [:table schema=cerebrum name=distribution_group]
            WHERE group_id=:g_id"""
            self.execute(delete_stmt, binds)
            self._db.log_change(self.entity_id,
                                self.clconst.dl_group_remove,
                                None,
                                change_params={'name': self.group_name,
                                               'roomlist': is_roomlist})
        return True

    def delete(self):
        """ Delete group, even if DistributionGroup. """
        self.demote_distribution()
        super(DistributionGroupMixin, self).delete()

    def get_extensions(self):
        """ Check if this group is a DistributionGroup. """
        exts = super(DistributionGroupMixin, self).get_extensions()
        try:
            self._is_roomlist()
        except Errors.NotFoundError:
            return exts
        return exts + ['DistributionGroup']
