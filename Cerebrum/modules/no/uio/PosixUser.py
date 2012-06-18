# -*- coding: iso-8859-1 -*-
# Copyright 2002-2006 University of Oslo, Norway
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
from Cerebrum.modules import PosixGroup, PosixUser  
from Cerebrum.modules.bofhd.auth import BofhdAuthOpSet, \
     BofhdAuthOpTarget, BofhdAuthRole

class PosixUserUiOMixin(PosixUser.PosixUser):
    """This mixin overrides PosixUser for the UiO instance,
    and automatically creates a personal file group for each
    user created. It also makes sure the group is deleted when
    POSIX is demoted for a user."""

    __read_attr__ = ('__in_db',)

    def delete_posixuser(self):
        """Demotes this PosixUser to a normal Account."""
        if self.entity_id is None:
            raise Errors.NoEntityAssociationError, \
                  "Unable to determine which entity to delete."
        self._db.log_change(self.entity_id, self.const.posix_demote,
                            None, change_params={'uid': int(self.posix_uid),
                                                 'gid': int(self.gid_id),
                                                 'shell': int(self.shell),
                                                 'gecos': self.gecos})
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=posix_user]
        WHERE account_id=:e_id""", {'e_id': self.entity_id})

        # Demote this PosixUsers personal group to a normal group
        # TODO: needs logic to ensure that the group is the personal
        # file group?
        primary_group = PosixGroup.PosixGroup(self._db)
        primary_group.find(self.gid_id)
        if primary_group.group_name == self.account_name:
            self.pg.delete()

    def populate(self, posix_uid, gid_id, gecos, shell, name=None,
                 owner_type=None, owner_id=None, np_type=None,
                 creator_id=None, expire_date=None, parent=None):
        """Populate PosixUser instance's attributes without database access."""
        if parent is not None:
            self.__xerox__(parent)
        else:
            self.__super.populate(posix_uid, gid_id, gecos, shell, name,
                                  owner_type, owner_id, np_type, creator_id,
                                  expire_date, parent)
        self.__in_db = False
        self.posix_uid = posix_uid
        self.gecos = gecos
        self.shell = shell

        self.pg = PosixGroup.PosixGroup(self._db)
        self.pg.populate(visibility=self.const.group_visibility_all,
                         name=name,
                         description=('Personal file group for %s' % name),
                             creator_id=creator_id)

    def write_db(self):
        """Write PosixUser instance to database."""
        # Writing group to DB
        try:
            self.pg.write_db()
            # We'll need to set this here, as the groups entity id is created
            # when we write to the DB.
            self.gid_id = self.pg.entity_id
        except self._db.DatabaseError, m:
            raise Errors.CerebrumError, "Database error: %s" % m

        # Writing the user to DB
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        primary_group = PosixGroup.PosixGroup(self._db)
        primary_group.find(self.gid_id)
        # TBD: should Group contain a utility function to add a member
        # if it's not a member already?  There are many occurences of
        # code like this, and but none of them implement all the
        # robustness below.
        if not primary_group.has_member(self.entity_id):
            primary_group.add_member(self.entity_id)

        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=posix_user]
              (account_id, posix_uid, gid, gecos, shell)
            VALUES (:a_id, :u_id, :gid, :gecos, :shell)""",
                         {'a_id': self.entity_id,
                          'u_id': self.posix_uid,
                          'gid': self.gid_id,
                          'gecos': self.gecos,
                          'shell': int(self.shell)})
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=posix_user]
            SET posix_uid=:u_id, gid=:gid, gecos=:gecos,
                shell=:shell
            WHERE account_id=:a_id""",
                         {'a_id': self.entity_id,
                          'u_id': self.posix_uid,
                          'gid': self.gid_id,
                          'gecos': self.gecos,
                          'shell': int(self.shell)})

        self._db.log_change(self.entity_id, self.const.posix_promote,
                            None, change_params={'uid': int(self.posix_uid),
                                                 'gid': int(self.gid_id),
                                                 'shell': int(self.shell),
                                                 'gecos': self.gecos})


        # Register the posixuser as owner of the group
        op_set = BofhdAuthOpSet(self._db)
        op_set.find_by_name(cereconf.BOFHD_AUTH_GROUPMODERATOR)
        op_target = BofhdAuthOpTarget(self._db)
        op_target.populate(self.pg.entity_id, 'group')
        op_target.write_db()
        role = BofhdAuthRole(self._db)
        role.grant_auth(self.entity_id, op_set.op_set_id,
                        op_target.op_target_id)

        # Add the posixuser to the group
        self.pg.add_member(self.entity_id)
       
        # Syncronizing the groups spreads with the users
        mapping = { int(self.const.spread_uio_nis_user):
                    int(self.const.spread_uio_nis_fg),
                    int(self.const.spread_uio_ad_account):
                    int(self.const.spread_uio_ad_group),
                    int(self.const.spread_ifi_nis_user):
                    int(self.const.spread_ifi_nis_fg) }
        wanted = []
        for r in self.get_spread():
            spread = int(r['spread'])
            if spread in mapping:
                wanted.append(mapping[spread])
        for r in self.pg.get_spread():
            spread = int(r['spread'])
            if not spread in mapping.values():
                pass
            elif spread in wanted:
                wanted.remove(spread)
            else:
                self.pg.delete_spread(spread)
        for spread in wanted:
            self.pg.add_spread(spread)

        # Return
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

