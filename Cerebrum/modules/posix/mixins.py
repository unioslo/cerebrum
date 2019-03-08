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
"""Base functionality for Posix objects.

The posix.mixins module contains mixins that should go into the base Account
and Group classes to support detection, deletion and cleanup of posix data.

"""
import cereconf

from Cerebrum import Errors
from Cerebrum.Group import Group
# from Cerebrum.Account import Account


class PosixGroupMixin(Group):

    """ Implementation of Posix group cleanup tasks.

    This class is intended as a mixin to the base Group class, to enable
    identification and cleanup of Posix Group data.

    """

    def _get_posix_gid(self):
        """ Fetch the posix GID if it exists.

        :return numerical: The GID of this posix group.

        :raise NotFoundError: If no posix GID exist.

        """
        return self.query_1("""SELECT posix_gid
        FROM [:table schema=cerebrum name=posix_group]
        WHERE group_id=:g_id""", {'g_id': self.entity_id})

    def demote(self):
        """ Remove all subclass-related data for the group. """
        res = self.demote_posix()
        return super(PosixGroupMixin, self).demote() or res

    def demote_posix(self):
        """ Remove all posix-related data for the group. """
        gid = None
        try:
            gid = self._get_posix_gid()
        except Errors.NotFoundError:
            return False

        self._db.log_change(self.entity_id,
                            self.clconst.posix_group_demote,
                            None,
                            change_params={'gid': int(gid), })

        self.execute("""
        DELETE FROM [:table schema=cerebrum name=posix_group]
        WHERE group_id=:g_id""", {'g_id': self.entity_id})
        return True

    def delete(self):
        """ Delete group, even if PosixGroup. """
        self.demote_posix()
        super(PosixGroupMixin, self).delete()

    def get_extensions(self):
        """ Check if this group is a PosixGroup. """
        exts = super(PosixGroupMixin, self).get_extensions()
        try:
            self._get_posix_gid()
        except Errors.NotFoundError:
            return exts
        return exts + ['PosixGroup']


# TODO: Implement?
#   class PosixAccountMixin(Account):
#       pass
