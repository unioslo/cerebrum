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

"""The ADAccount module is used as a mixin-class for ADObject, and
contains additional parameters that are required for building Accounts in
Active Directory.  The ADAccount defines new values for the users in ad;
login script and home directory.

The user name is inherited from the superclass, which here is ADObject."""

import string
import cereconf
from Cerebrum import Utils
from Cerebrum import Constants, Errors
from Cerebrum.modules.ADObject import ADObject


class ADAccount(ADObject):
# Arve egenskaper fra ADObject.

   
    __read_attr__ = ('__in_db',)
    __write_attr__ = ('login_script', 'home_dir',)

    def clear(self):
        self.__super.clear()
        for attr in ADAccount.__read_attr__:
            if hasattr(self, attr):
                delattr(self, attr)
        for attr in ADAccount.__write_attr__:
            setattr(self, attr, None)
        self.__updated = False

    def __eq__(self, other):
        assert isinstance(other, ADUser)
        if self.ou_id   == other.ou_id:
            return self.__super.__eq__(other)
        return False


    def find(self, account_id):
        """Associate the object with the ADUser whose identifier is account_id.

        If account_id isn't an existing ID identifier,
        NotFoundError is raised."""
        self.__super.find(account_id)
        (self.login_script, self.home_dir) = self.query_1("""
        SELECT login_script,home_dir
        FROM [:table schema=cerebrum name=ad_account]
        WHERE account_id=:account_id""", {'account_id': account_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = False


