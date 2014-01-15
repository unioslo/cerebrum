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


import re
import cereconf

from Cerebrum import Group
from Cerebrum import Utils
from Cerebrum.Database import Errors

class GroupUiOMixin(Group.Group):
    """Group mixin class providing functionality specific to UiO.
    """

    def add_member(self, member_id):
        '''Override default add_member with checks that avoids
        membership in too many PosixGroups of the same spread as this
        gives problems with NFS

        @param member_id: Cf. L{Group.Group.add_member}
        '''

        from Cerebrum.modules import PosixGroup

        # TODO: we should include_indirect_members

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
        for g in self.search(member_id=member_id,
                             indirect_members=False,
                             filter_expired=False):
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
        super(GroupUiOMixin, self).add_member(member_id)

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
                raise self._db.IntegrityError, \
                      "Can't add NIS-spread to non-posix group."
            tmp = pg.illegal_name(pg.group_name)
            if tmp:
                raise self._db.IntegrityError, \
                      "Illegal name for filegroup, %s." % tmp
        #
        # (Try to) perform the actual spread addition.
        ret = self.__super.add_spread(spread)

    # helper methods for AD/Exchange security groups
    # make fetching group data for Exchange consistent (between
    # security groups and distribution groups)
    def get_secgroup_data(self, group_id):
        all_data = {}
        sec_group = Utils.Factory.get("Group")(self._db)
        try:
            sec_group.find(group_id)
        except Errors.NotFoundError:
            return None
        all_data = {'name': sec_group.group_name,
                    'group_id': sec_group.entity_id,
                    'description': sec_group.description}
        return all_data

    # sec-group create, will do all necessary checks and actions
    # here
    def make_secgroup(self, group_id):
        sec_group = Utils.Factory.get("Group")(self._db)
        try:
            # only existing groups may be made into security groups
            sec_group.find(group_id)
        except Errors.NotFoundError:
            return
        # group name must not contain illegal char or be longer than 
        # 64 char
        if re.search("[^a-z0-9\-\.]", str(sec_group.group_name)) or \
                self.illegal_name(sec_group.group_name, max_length=64):
            return "Illegal name for security group %s" % sec_group.group_name 
        sec_group.add_spread(self.const.Spread(cereconf.SECGROUP_SPREAD))
        sec_group.write_db()
        return "Will export security group %s to Exchange" % sec_group.group_name
    # exchange-relatert-jazz
    # add som name checks that are related to group name requirements
    # in AD/Exchange. 
    def illegal_name(self, name, max_length=32):
        # no group names should start with a period or a space!
        if re.search("^\.|^\s", name):
            return "Names cannot start with period or space (%s)" % name 
        # Avoid circular import dependency
        from Cerebrum.modules import PosixGroup
        from Cerebrum.modules.exchange.v2013 import ExchangeGroups

        if isinstance(self, PosixGroup.PosixGroup):
            if len(name) > max_length:
                return "name too long (%s characters; %d is max)" % (len(name), max_length)
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
