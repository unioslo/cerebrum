# Copyright 2002 University of Oslo, Norway
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

"""The PosixUser module is used as a mixin-class for Account, and
contains additional parameters that are required for building password
maps used in Unix.  This includes UID, GID, Shell, gecos and home
directory.

The module in itself does not define which domain the entity_name
representing the username is stored in, as the module cannot know
which domain is currently being processed.  The routines generating
the password map, and building new users have this information.

If no posix username is defined for a given domain, the user is
considered to not be a member of the given domain.  That is, the
default username from Account is NOT used.

When the gecos field is not set, it is automatically extracted from
the name variant DEFAULT_GECOS_NAME (what about non-person accounts?).
SourceSystems are evaluated in the order defined by
POSIX_GECOS_SS_ORDER"""

import random
from Cerebrum import Person,Constants,Errors
from Cerebrum import cereconf

class PosixUser(object):
    "Mixin class for Account"

    def clear(self):
        super(PosixUser, self).clear()
        self.user_uid = None
        self.gid = None
        self.gecos = None
        self.home = None
        self.shell = None

    def __eq__(self, other):
        if self._pn_affect_source == None:
            return True
        assert isinstance(other, PosixUser)
        return True

    def populate_posix_user(self, user_uid, gid, gecos, home, shell):
        self.user_uid = user_uid
        self.gid = gid
        self.gecos = gecos
        self.home = home
        self.shell = shell

    def write_db(self, as_object=None):
        self.execute("""
        INSERT INTO cerebrum.posix_user (account_id, user_uid, gid,
               gecos, home, shell)
        VALUES (:a_id, :u_id, :gid, :gecos, :home, :shell)""",
                     {'a_id' : self.account_id, 'u_id' : self.user_uid,
                      'gid' : self.gid, 'gecos' : self.gecos,
                      'home' : self.home, 'shell' : int(self.shell)})

    def find_posixuser(self, account_id):
        (self.account_id, self.user_id, self.gid, self.gecos,
         self.home, self.shell) = self.query_1(
            """SELECT account_id, user_uid, gid, gecos, home, shell
               FROM cerebrum.posix_user
               WHERE account_id=:a_id""", {'a_id' : account_id})

    def get_all_posix_users(self):
        return self.query("SELECT account_id FROM posix_user")

    def get_free_uid(self):
        random.randint(0,1000000)

    # get_free_uid = staticmethod(get_free_uid)

    def get_gecos(self):
        assert self.owner_type == int(self.const.entity_person)
        p = Person.Person(self._db)
        p.find(self.owner_id)
        for ss in cereconf.POSIX_GECOS_SS_ORDER:
            try:
               ret = p.get_name(getattr(self.const, ss),
                                getattr(self.const, cereconf.DEFAULT_GECOS_NAME))
               return ret
            except Errors.NotFoundError:
                pass
        return "Unknown"
