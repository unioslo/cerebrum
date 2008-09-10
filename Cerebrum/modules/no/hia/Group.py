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
from Cerebrum.Utils import Factory
from Cerebrum.Database import Errors

class GroupHiAMixin(Group.Group):
    """Group mixin class providing functionality specific to HiA.
    """
    def add_member(self, member_id):
        '''Override default add_member with checks that avoids
        membership in more than one eDir server-group'''

        server_groups = ['server-ulv',
                         'server-laks',
                         'server-uer',
                         'server-abbor',
                         'server-rev',
                         'server-orrhane',
                         'server-rype']
        group = Factory.get("Group")(self._db)
        dest_group = Factory.get("Group")(self._db)
        try:
            dest_group.clear()
            dest_group.find(self.entity_id)
        except Errors.NotFoundError:
            raise self._db.IntegrityError, \
                  'Cannot add members to a non-existing group!'
        dest_group_name = dest_group.group_name
        account = Factory.get("Account")(self._db)
        member_type = self.query_1("""
            SELECT entity_type
            FROM [:table schema=cerebrum name=entity_info]
            WHERE entity_id = :member_id""", {"member_id": member_id})
        if (member_type == int(self.const.entity_account) and
            dest_group_name in server_groups):
            account.clear()
            account.find(member_id)
            for g in server_groups:
                group.clear()
                group.find_by_name(g)
                if group.has_member(member_id):
                    raise self._db.IntegrityError(
                        "Member of a eDir server group already (%s)" % g)
        super(GroupHiAMixin, self).add_member(member_id)
        
    def add_spread(self, spread):
        # FIXME, jazz 2008-07-28: we should move this check into PosixGroup
        # and establish a cereconf.POSIX_GROUP_SPREAD or something
        # Avoid circular import dependency
        from Cerebrum.modules import PosixGroup

        # When adding a NIS-spread, assert that group is a PosixGroup
        if int(spread) in (self.const.spread_nis_fg,
                           self.const.spread_ans_nis_fg):
            pg = PosixGroup.PosixGroup(self._db)
            try:
                pg.clear()
                pg.find(self.entity_id)
            except Errors.NotFoundError:
                raise self._db.IntegrityError, \
                      "Can't add NIS-spread to non-posix group."
            tmp = pg.illegal_name(pg.group_name)
            if tmp:
                raise self._db.IntegrityError, \
                      "Illegal name for filegroup, %s." % tmp                
        #
        # (Try to) perform the actual spread addition.
        ret = self.__super.add_spread(spread)

    def illegal_name(self, name):
        # Avoid circular import dependency
        from Cerebrum.modules import PosixGroup

        if isinstance(self, PosixGroup.PosixGroup):
            if len(name) > 8:
                return "name too long (%d characters)" % len(name)
            if re.search("^[^a-z]", name):
                return "name must start with a character (%s)" % name
            if re.search("[^a-z0-9\-_]", name):
                return "name contains illegal characters (%s)" % name
        return False
