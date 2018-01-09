# -*- coding: utf-8 -*-
# Copyright 2003-2018 University of Oslo, Norway
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


import re

from Cerebrum import Group
from Cerebrum.database import Errors
from Cerebrum.modules import Email


class GroupUiOMixin(Group.Group):
    """Group mixin class providing functionality specific to UiO.
    """

    def add_spread(self, spread):
        # Avoid circular import dependency
        from Cerebrum.modules import PosixGroup
        # When adding a NIS-spread, assert that group is a PosixGroup
        if int(spread) in (self.const.spread_uio_nis_fg,
                           self.const.spread_ifi_nis_fg,
                           self.const.spread_hpc_nis_fg):
            pg = PosixGroup.PosixGroup(self._db)
            try:
                pg.clear()
                pg.find(self.entity_id)
            except Errors.NotFoundError:
                raise Errors.RequiresPosixError(
                    "Can't add NIS-spread to non-POSIX group.")
            tmp = pg.illegal_name(pg.group_name)
            if tmp:
                raise self._db.IntegrityError(
                    "Illegal name for filegroup, {0}.".format(tmp))
        # When adding a Shared mailbox spread, assert that the group is a
        # distribution group.
        if spread == self.const.spread_exchange_shared_mbox:
            if not self.has_spread(self.const.spread_exchange_group):
                raise Errors.CerebrumError(
                    "Can't add shared mailbox spread to a "
                    "non-distribution group")
        #
        # (Try to) perform the actual spread addition.
        self.__super.add_spread(spread)

    # exchange-relatert-jazz
    # add som name checks that are related to group name requirements
    # in AD/Exchange.
    def illegal_name(self, name, max_length=32):
        if len(name) == 0:
            return "Must specify group name"
        # no group names should start with a period or a space!
        if re.search("^\.|^\s", name):
            return "Names cannot start with period or space (%s)" % name
        # Avoid circular import dependency
        from Cerebrum.modules import PosixGroup
        from Cerebrum.modules.exchange import ExchangeGroups

        # TODO: Why? Should this not be implemented as a illegal_name on
        # PosixGroup?
        if isinstance(self, PosixGroup.PosixGroup):
            if len(name) > max_length:
                return ("name too long ({name_length} characters; "
                        "{max_length} is max)".format(
                            name_length=len(name), max_length=max_length))
            if re.search("^[^a-z]", name):
                return "name must start with a character (%s)" % name
            if re.search("[^a-z0-9\-_]", name):
                return "name contains illegal characters (%s)" % name
        elif isinstance(self, ExchangeGroups.DistributionGroup):
            # allow [a-z0-9], '-' and '.' in DistributionGroup names
            if re.search("[^a-z0-9\-\.]", name):
                return "name contains illegal characters (%s)" % name
            # ad-groups may have names up to 64 char long
            if len(name) > 64:
                return "Name %s too long (64 char allowed)" % name
        return False

    def delete(self):
        """Delete the group, along with its EmailTarget."""
        et = Email.EmailTarget(self._db)
        ea = Email.EmailAddress(self._db)
        epat = Email.EmailPrimaryAddressTarget(self._db)

        # If there is not associated an EmailTarget with the group, call delete
        # from the superclass.
        try:
            et.find_by_target_entity(self.entity_id)
        except Errors.NotFoundError:
            return super(GroupUiOMixin, self).delete()

        # An EmailTarget exists, so we try to delete its primary address.
        try:
            epat.find(et.entity_id)
            epat.delete()
        except Errors.NotFoundError:
            pass

        # We remove all the EmailTargets addresses.
        try:
            for row in et.get_addresses():
                ea.clear()
                ea.find(row['address_id'])
                ea.delete()
        except Errors.NotFoundError:
            pass

        # Delete the EmailTarget
        et.delete()

        # Finally! Delete the group!
        super(GroupUiOMixin, self).delete()
