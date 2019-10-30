#!/user/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2013 University of Oslo, Norway
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
"""TSD specific behaviour for posix users."""

from mx import DateTime

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import PosixUser  

class PosixUserTSDMixin(PosixUser.PosixUser):
    """This mixin overrides PosixUser for the TSD instance, where all users are
    members of one and only one project. All members of the same project have
    the same default file group.

    """

    def __init__(self, database):
        self.pg = Factory.get('PosixGroup')(database)
        self.__super.__init__(database)

    def clear(self):
        self.pg.clear()
        return self.__super.clear()

    def find(self, account_id):
        """Connect the posixuser with the corresponding posixgroup."""
        ret = self.__super.find(account_id)
        self.pg.find(self.gid_id)
        return ret

    def populate(self, posix_uid, gid_id, gecos, shell, name=None,
                 owner_type=None, owner_id=None, np_type=None, creator_id=None,
                 expire_date=None, parent=None):
        """Populate PosixUser instance's attributes without database access.

        TODO: rewrite this, was for UiO:
        Note that the given L{gid_id} is ignored, the account's personal file
        group is used anyways. The personal group's entity_id will be fetched at
        L{write_db}.

        Note that the gid_id could be forced by explicitly setting pu.gid_id
        after populate. The module would then respect this at write_db.

        """
        assert name or parent, "Need to either specify name or parent"
        aname = name or parent.account_name

        # The suffix could be implemented as a cereconf variable, if needed by
        # other Posix classes.
        groupname = '%s-group' % aname

        self.pg.clear()
        try:
            self.pg.find_by_name(groupname)
        except Errors.NotFoundError:
            self.pg.populate(
                visibility=self.const.group_visibility_all,
                name=groupname,
                creator_id=creator_id,
                description=('Personal file group for %s' % aname),
                group_type=self.const.group_type_personal,
            )

        # The gid_id is not given to the super class, but should be set at
        # write_db, when we have the group's entity_id.
        return self.__super.populate(posix_uid, None, gecos, shell, name,
                                     owner_type, owner_id, np_type, creator_id,
                                     expire_date, parent)

    def write_db(self):
        """Write PosixUser instance to database, in addition to the personal
        file group. As long as L{gid_id} is not set, it gets set to the
        account's personal file group instead.

        """
        self.pg.write_db()
        if not self.gid_id:
            # TODO: Should we handle that self.pg could not be populated when
            # we're here? When could gid_id be none without running populate?

            # We need to set this here, as the groups entity_id is not created
            # until first time we write to the DB:
            self.gid_id = self.pg.entity_id
        ret = self.__super.write_db()

        # Become a member of the group:
        if not self.pg.has_member(self.entity_id):
            self.pg.add_member(self.entity_id)

        # Update the group's spreads:
        self._synchronize_posix_spreads()
        # Affiliate the group:
        self._assert_group_project_affiliation()
        return ret

    def add_spread(self, *args, **kwargs):
        """Override with TSD specific behaviour."""
        ret = self.__super.add_spread(*args, **kwargs)
        self._synchronize_posix_spreads()
        self._assert_group_project_affiliation()
        return ret

    def delete_spread(self, spread):
        """Override with TSD specific behaviour."""
        ret = self.__super.delete_spread(spread)
        self._synchronize_posix_spreads()
        self._assert_group_project_affiliation()
        return ret

    def _synchronize_posix_spreads(self):
        """Synchronize the user's spreads with the personal group's.

        TODO: Should we do this for regular Accounts as well and not just POSIX
        users?

        """
        mapping = {int(self.const.spread_ad_account):
                       (int(self.const.spread_file_group),),
                   }
        user_spreads = [int(r['spread']) for r in self.get_spread()]
        group_spreads = [int(r['spread']) for r in self.pg.get_spread()]
        for uspr, gsprs in mapping.iteritems():
            if uspr in user_spreads:
                for gspr in gsprs:
                    if gspr not in group_spreads:
                        self.pg.add_spread(gspr)
            else:
                for gspr in gsprs:
                    if gspr in group_spreads:
                        self.pg.delete_spread(gspr)

    def _assert_group_project_affiliation(self):
        """Make sure the group is affiliated with the TSD project.

        The trait will not be updated if already set, as we assume that it is
        correct.

        """
        if not self.pg.get_trait(self.const.trait_project_group):
            try:
                ou_id = self.get_tsd_project_id()
            except Errors.NotFoundError:
                pass
            else:
                self.pg.populate_trait(self.const.trait_project_group,
                                       target_id=ou_id,
                                       date=DateTime.now())
                self.pg.write_db()
