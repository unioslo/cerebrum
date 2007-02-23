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
from Cerebrum import Errors
from Cerebrum.Utils import Factory

class UidRangeException(Exception):
    """Exception raised for Uids out of legal range"""
    pass

class PosixUserNTNUMixin(PosixUser.PosixUser):
    allranges = [
        (1000, 50000),
        (53001, 65000),
        (1048576, 2097152)
        ]
    currentrange = (1048576, 2097152)
    
    def _reset_uid_sequence_hack(self, min, max):
        # We're resetting the sequence ourselves. Ugly!
        # Postgres-spesific!
        self.execute("""ALTER SEQUENCE posix_uid_seq
        MINVALUE :min MAXVALUE :max
        RESTART :min INCREMENT 1""", locals())
        
    def get_free_uid(self):
        uid=self.__super.get_free_uid()
        if uid<self.currentrange[0] or uid>self.currentrange[1]:
            self._reset_uid_sequence_hack(self.currentrange[0],
                                          self.currentrange[1])
            uid=self.__super.get_free_uid()
            if uid<=self.currentrange[0] or uid>=self.currentrange[1]:
                raise UidRangeException(
                    "Uid out of range: Please reset posix_uid_seq to %d" %
                    self.currentrange[0])
        return uid
        
    def illegal_uid(self, uid):
        # All uids outside allranges is disallowed, also when set manually.
        for r in self.allranges:
            if r[0] < uid and uid < r[1]:
                # self.__super.illegal_uid(uid)
                return None
        return "Uid (%d) out of NTNU ranges." % uid

    def write_db(self):
        tmp=self.illegal_uid(self.posix_uid)
        if tmp:
            raise self._db.IntegrityError, "Illegal Posix UID: %s" % tmp
        self.__super.write_db()
