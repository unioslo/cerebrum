# -*- coding: iso-8859-1 -*-

# Copyright 2006 University of Oslo, Norway
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

from Cerebrum.modules import PosixUser

class UidRangeException(Exception):
    """Exception raissed for Uids out of legal range"""
    pass


# This probably behaves badly if all uids in range are used.
class PosixUserNoturMixin(PosixUser.PosixUser):
    #Gah! BDB uses 50001-53000 inclusive.
    #But others may believe 50000-52999 inclusive.
    #Be safe.
    minuid = 50001
    maxuid = 52999
    #Autogenerate uids outside those currently used by BDB, Check!
    minfreeuid = 51500
    maxfreeuid = 52999
    
    def get_free_uid(self):
        uid=self.__super.get_free_uid()
        if uid<self.minfreeuid or uid>self.maxfreeuid:
            # We're resetting the sequence ourselves. Ugly!
            # Postgres-spesific!
            self.execute("""ALTER SEQUENCE posix_uid_seq
            MINVALUE :min MAXVALUE :max
            RESTART :min INCREMENT 1""",
                         {'min': self.minfreeuid,
                          'max': self.maxfreeuid})
            uid=self.__super.get_free_uid()
            if uid<=self.minfreeuid or uid>=self.maxfreeuid:
                raise UidRangeException(
                    "Uid out of range: Please reset posix_uid_seq to %d" %
                    minfreeuid)
        return uid

    def illegal_uid(self, uid):
        # All uids outside NOTUR range is disallowed, also when set manually.
        if uid<self.minuid or uid>self.maxuid:
            return "Uid (%d) of of NOTUR range." % uid
        # self.__super.illegal_uid(uid)

    def write_db(self):
        tmp=self.illegal_uid(self.posix_uid)
        if tmp:
            raise self._db.IntegrityError, "Illegal Posix UID: %s" % tmp
        self.__super.write_db()

