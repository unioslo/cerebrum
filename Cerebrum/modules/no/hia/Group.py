# -*- coding: iso-8859-1 -*-
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
import cereconf

from Cerebrum import Errors, Group
from Cerebrum.Utils import Factory


class GroupHiAMixin(Group.Group):
    def add_spread(self, spread):
        # FIXME, jazz 2008-07-28: we should move this check into PosixGroup
        # and establish a cereconf.POSIX_GROUP_SPREAD or something
        # Avoid circular import dependency
        from Cerebrum.modules import PosixGroup

        # When adding a NIS-spread, assert that group is a PosixGroup
        if int(spread)  == self.const.spread_nis_fg:
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
        #
        # (Try to) perform the actual spread addition.
        ret = self.__super.add_spread(spread)

    def illegal_name(self, name):
        # Avoid circular import dependency
        from Cerebrum.modules import PosixGroup

        if len(name) == 0:
            return "Must specify group name"

        if isinstance(self, PosixGroup.PosixGroup):
            if len(name) > 32:
                return "name too long (%d characters)" % len(name)
            if re.search("^[^a-z]", name):
                return "name must start with a character (%s)" % name
            if re.search("[^a-z0-9\-_]", name):
                return "name contains illegal characters (%s)" % name
        return False
