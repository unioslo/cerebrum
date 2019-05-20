# -*- coding: utf-8 -*-
# Copyright 2002-2019 University of Oslo, Norway
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

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import PosixUser
from Cerebrum.modules.bofhd.auth import (BofhdAuthOpSet,
                                         BofhdAuthOpTarget,
                                         BofhdAuthRole)


class PosixUserUiTMixin(PosixUser.PosixUser):
    """This mixin overrides PosixUser for the UiT instance, and automatically
    creates a personal file group for each user created. It also makes sure
    the group is deleted when POSIX is demoted for a user.

    """

    def __init__(self, database):
        self.pg = Factory.get('PosixGroup')(database)
        self.__super.__init__(database)

    def delete_posixuser(self):
        """Demotes this PosixUser to a normal Account. Overridden to also
        demote the PosixUser's file group to a normal group, as long as it is
        the account's personal group.

        """
        ret = self.__super.delete_posixuser()

        self.pg.clear()
        self.pg.find(self.gid_id)

        # TODO: check personal_group trait instead or in addition
        if self.pg.group_name == self.account_name:
            if (hasattr(self, 'delete_trait') and
                    self.get_trait(self.const.trait_personal_dfg)):
                self.delete_trait(self.const.trait_personal_dfg)
                self.write_db()
            for row in self.pg.get_spread():
                self.pg.delete_spread(int(row['spread']))
            self.pg.write_db()
            self.pg.delete()
        return ret

    def clear(self):
        """Also clear the PosixGroup."""
        self.pg.clear()
        return self.__super.clear()

    def populate(self, posix_uid, gid_id, gecos, shell,
                 name=None, owner_type=None, owner_id=None, np_type=None,
                 creator_id=None, expire_date=None, parent=None):
        """Populate PosixUser instance's attributes without database access.
        Note that the given L{gid_id} is ignored, the account's personal file
        group is used anyways. The personal group's entity_id will be fetched
        at L{write_db}.

        Note that the gid_id could be forced by explicitly setting pu.gid_id
        after populate. The module would then respect this at write_db.

        """
        assert name or parent, "Need to either specify name or parent"

        if not creator_id:
            creator_id = parent.entity_id

        self.pg.clear()
        try:
            self.pg.find_by_name(name or parent.account_name)
        except Errors.NotFoundError:
            self.pg.populate(visibility=self.const.group_visibility_all,
                             name=name or parent.account_name,
                             creator_id=creator_id,
                             description=('Personal file group for %s' % name))

        # The gid_id is not given to the super class, but should be set at
        # write_db, when we have the group's entity_id.
        return self.__super.populate(posix_uid, None, gecos, shell, name,
                                     owner_type, owner_id, np_type, creator_id,
                                     expire_date, parent)

    def map_user_spreads_to_pg(self, group=None):
        super(PosixUserUiTMixin, self).map_user_spreads_to_pg(group=group)

        if group is None:
            return

        # Syncronizing the groups spreads with the users
        mapping = [
            (int(self.const.spread_uit_nis_user),
             int(self.const.spread_uit_nis_fg)),
            (int(self.const.spread_uit_ad_account),
             int(self.const.spread_uit_ad_group)),
            (int(self.const.spread_ifi_nis_user),
             int(self.const.spread_ifi_nis_fg)),
        ]
        user_spreads = [int(r['spread']) for r in self.get_spread()]
        group_spreads = [int(r['spread']) for r in group.get_spread()]
        for uspr, gspr in mapping:
            if uspr in user_spreads and gspr not in group_spreads:
                group.add_spread(gspr)
            if gspr in group_spreads and uspr not in user_spreads:
                group.delete_spread(gspr)

    def _set_owner_of_group(self, group):
        op_target = BofhdAuthOpTarget(self._db)
        if not op_target.list(entity_id=group.entity_id, target_type='group'):
            op_target.populate(group.entity_id, 'group')
            op_target.write_db()
            op_set = BofhdAuthOpSet(self._db)
            op_set.find_by_name(cereconf.BOFHD_AUTH_GROUPMODERATOR)
            role = BofhdAuthRole(self._db)
            role.grant_auth(self.entity_id,
                            op_set.op_set_id,
                            op_target.op_target_id)

    def write_db(self):
        """Write PosixUser instance to database, in addition to the personal
        file group. As long as L{gid_id} is not set, it gets set to the
        account's personal file group instead.

        """
        if not self.gid_id:
            # Create the PosixGroup first, to get its entity_id
            # TODO: Should we handle that self.pg could not be populated when
            # we're here? When could gid_id be none without running populate?
            self.pg.write_db()
            # We'll need to set this here, as the groups entity_id is
            # created when we write to the DB.
            self.gid_id = self.pg.entity_id

        ret = self.__super.write_db()

        # Become a member of the group:
        if not hasattr(self.pg, 'entity_id'):
            self.pg.find(self.gid_id)
        if not self.pg.has_member(self.entity_id):
            self.pg.add_member(self.entity_id)

        # If the dfg is not a personal group we are done now:
        # TODO: check trait_personal_dfg instead or in addition?
        if self.account_name != self.pg.group_name:
            return ret

        # Set the personal file group trait
        # TODO: This can't be right? UiT uses a common file group, posixgroup
        if not self.pg.get_trait(self.const.trait_personal_dfg):
            self.pg.populate_trait(self.const.trait_personal_dfg,
                                   target_id=self.entity_id)
            self.pg.write_db()

        # Register the posixuser as owner of the group, if not already set
        self._set_owner_of_group(self.pg)

        # Syncronizing the groups spreads with the users
        self.map_user_spreads_to_pg(group=self.pg)
        return ret
