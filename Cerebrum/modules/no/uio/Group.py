# -*- coding: iso-8859-1 -*-
# Copyright 2003 University of Oslo, Norway
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

""""""

import re
import cereconf

from Cerebrum import Group
from Cerebrum.Database import Errors

class GroupUiOMixin(Group.Group):
    """Group mixin class providing functionality specific to UiO.
    """

    def add_member(self, member_id, type, op):
        '''Override default add_member with checks that avoids
        membership in too many PosixGroups of the same spread as this
        gives problems with NFS'''

        from Cerebrum.modules import PosixGroup

        # TODO: we should look at op, and include_indirect_members

        group_spreads = [int(s['spread']) for s in self.get_spread()]
        relevant_spreads = []
        for name in cereconf.NIS_SPREADS:
            c = getattr(self.const, name)
            if int(c) in group_spreads:
                relevant_spreads.append(int(c))
        counts = {}
        for s in relevant_spreads:
            counts[s] = 0

        pg = PosixGroup.PosixGroup(self._db)
        for g in self.list_groups_with_entity(member_id):
            try:
                pg.clear()
                pg.find(g['group_id'])
                for s in pg.get_spread():
                    if int(s['spread']) in relevant_spreads:
                        counts[int(s['spread'])] += 1
            except Errors.NotFoundError:
                pass
        for k in counts.keys():
            if counts[k] > 16:
                raise self._db.IntegrityError(
                    "Member of too many groups (%i)" % counts[k])
        super(GroupUiOMixin, self).add_member(member_id, type, op)

    def add_spread(self, spread):
        # Avoid circular import dependency
        from Cerebrum.modules import PosixGroup

        # When adding a NIS-spread, assert that group is a PosixGroup
        if int(spread) in (self.const.spread_uio_nis_fg,
                           self.const.spread_ifi_nis_fg):
            pg = PosixGroup.PosixGroup(self._db)
            try:
                pg.clear()
                pg.find(self.entity_id)
            except Errors.NotFoundError:
                raise self._db.IntegrityError, \
                      "Can't add NIS-spread to non-posix group."
        #
        # (Try to) perform the actual spread addition.
        ret = self.__super.add_spread(spread)

    def illegal_name(self, name):
        # Avoid circular import dependency
        from Cerebrum.modules import PosixGroup

        if isinstance(self, PosixGroup.PosixGroup):
            if len(name) > 8:
                return "too long (%s)" % name
            if re.search("^[^a-z]", name):
                return "must start with a character (%s)" % name
            if re.search("[^a-z0-9\-_]", name):
                return "contains illegal characters (%s)" % name
        return False

# arch-tag: ed190fbb-c85a-4b09-820d-4296aa7b4197
