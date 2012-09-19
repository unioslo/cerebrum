#!/user/bin/env python
# -*- coding: iso-8859-1 -*-
# Copyright 2002-2012 University of Oslo, Norway
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
from Cerebrum.modules.bofhd.auth import BofhdAuthOpSet, \
     BofhdAuthOpTarget, BofhdAuthRole

class PosixUserUiOMixin(PosixUser.PosixUser):
    """This mixin overrides PosixUser for the UiO instance, and automatically
    creates a personal file group for each user created. It also makes sure
    the group is deleted when POSIX is demoted for a user.

    """

    __read_attr__ = ('__in_db',)

    def __init__(self, database):
        self.__super.__init__(database)
        self.pg = Factory.get('PosixGroup')(self._db)

    def delete_posixuser(self):
        """Demotes this PosixUser to a normal Account. Overridden to also
        demote the PosixUser's file group to a normal group, as long as it is
        the account's personal group.

        """
        ret = self.__super.delete_posixuser()
        self.pg.clear()
        self.pg.find(self.gid_id)
        if self.pg.group_name == self.account_name:
            self.pg.delete()
        return ret

    def populate(self, posix_uid, gid_id, gecos, shell, name=None, owner_type=None,
                 owner_id=None, np_type=None, creator_id=None, expire_date=None,
                 parent=None):
        """Populate PosixUser instance's attributes without database access.
        Note that the given L{gid_id} is ignored, the account's personal file
        group is used anyways. The personal group's entity_id will be fetched at
        L{write_db}.

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

    def write_db(self):
        """Write PosixUser instance to database, in addition to the personal
        file group. As long as L{gid_id} is not set, it gets set to the
        account's personal file group instead.

        """
        if not self.gid_id:
            # Create the PosixGroup first, to get its entity_id
            # TODO: Should we handle that self.pg could not be set?
            try:
                self.pg.write_db()
                # We'll need to set this here, as the groups entity_id is created
                # when we write to the DB.
                self.gid_id = self.pg.entity_id
            except self._db.DatabaseError, m:
                raise Errors.CerebrumError("Database error: %s" % m)

        ret = self.__super.write_db()

        # Become a member of the group:
        if not hasattr(self.pg, 'entity_id'):
            self.pg.find(self.gid_id)
        if not self.pg.has_member(self.entity_id):
            self.add_member(self.entity_id)

        # If the dfg is not a personal group we are done now:
        if self.account_name != self.pg.group_name:
            return ret

        # Register the posixuser as owner of the group, if not already set
        op_target = BofhdAuthOpTarget(self._db)
        if not op_target.list(entity_id=self.pg.entity_id, target_type='group'):
            op_target.populate(self.pg.entity_id, 'group')
            op_target.write_db()
            op_set = BofhdAuthOpSet(self._db)
            op_set.find_by_name(cereconf.BOFHD_AUTH_GROUPMODERATOR)
            role = BofhdAuthRole(self._db)
            role.grant_auth(self.entity_id, op_set.op_set_id,
                            op_target.op_target_id)

        # Syncronizing the groups spreads with the users
        mapping = { int(self.const.spread_uio_nis_user):
                    int(self.const.spread_uio_nis_fg),
                    int(self.const.spread_uio_ad_account):
                    int(self.const.spread_uio_ad_group),
                    int(self.const.spread_ifi_nis_user):
                    int(self.const.spread_ifi_nis_fg) }
        user_spreads = [int(r['spread']) for r in self.get_spread()]
        group_spreads = [int(r['spread']) for r in self.pg.get_spread()]
        for uspr, gspr in mapping.iteritems():
            if uspr in user_spreads:
                if gspr not in group_spreads:
                    self.pg.add_spread(gspr)
            elif gspr in group_spreads:
                self.pg.delete_spread(spread)

        return ret
