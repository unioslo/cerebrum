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

"""

"""

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
