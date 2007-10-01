# -*- coding: iso-8859-1 -*-

# Copyright 2007 University of Oslo, Norway
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

from Cerebrum import Account
from Cerebrum import Errors
#from Cerebrum.modules import PosixUser
from Cerebrum.Utils import Factory
from Cerebrum.modules.PasswordChecker import PasswordGoodEnoughException

import re
import random


# Todo: create a local module to store these rules.

posix_spreads=(
    "user@ansatt",
    "user@stud"
    )

spread_homedirs = {
    "user@ansatt":
    [  ("/home/ahomea", 1),
       ("/home/ahomeb", 1),
       ("/home/ahomec", 1),
       ("/home/ahomed", 1),
       ("/home/ahomee", 1),
       ("/home/ahomef", 1) ],
    "user@stud":
    [  ("/home/shomeo", 1),
       ("/home/shomep", 1),
       ("/home/shomeq", 1),
       ("/home/shomer", 1),
       ("/home/shomes", 1),
       ("/home/shomet", 1) ]
    }


account_name_regex=re.compile("^[a-z][a-z0-9]*$")

class AccountNTNUMixin(Account.Account):
    def illegal_name(self, name):
        if len(name) > 8:
            return "too long (%s)" % name
        if not re.match(account_name_regex, name):
            return "misformed (%s)" % name
        return self.__super.illegal_name(name)


    def is_posix(self):
        from Cerebrum.modules.PosixUser import PosixUser
        try:
            tmp=PosixUser(self._db)
            tmp.find(self.entity_id)
            return True
        except Errors.NotFoundError:
            return False
        
    def add_spread(self, spread):
        from Cerebrum.modules.PosixUser import PosixUser
        if (str(self.const.Spread(spread)) in posix_spreads
            and not isinstance(self, PosixUser)
            and not self.is_posix()):
            raise Errors.RequiresPosixError

        self.__super.add_spread(spread)

        if spread_homedirs.has_key(str(self.const.Spread(spread))):
            if not self.has_homedir(spread):
                self.make_homedir(spread)

    def has_homedir(self, spread):
        try:
            return self.get_home(spread)
        except Errors.NotFoundError:
            return False

    def make_homedir(self, spread):
        all_disks = spread_homedirs[str(self.const.Spread(spread))]
        avail_disks = [d[0] for d in all_disks if d[1]]
        diskpath = random.choice(avail_disks)
        disk = Factory.get('Disk')(self._db)
        disk.find_by_path(diskpath)
        homedir = self.set_homedir(disk_id=disk.entity_id,
                                status=self.const.home_status_not_created)
        self.set_home(spread, homedir)

    home_path_regex=re.compile("^(/[a-z0-9][a-z0-9_-]*)+$")
    rest_path_regex=re.compile("^(/?[a-z0-9][a-z0-9_-]*)+$")
    def set_homedir(self, **kw):
        regex=self.home_path_regex
        if kw.get("disk_id") is not None:
            regex=self.rest_path_regex
        if kw.get("home") is not None:
            if not regex.match(kw["home"]):
                raise self._db.IntegrityError, "Illegal home path"
        return self.__super.set_homedir(**kw)

    def encrypt_password(self, method, plaintext, salt=None):
        if method == self.const.auth_type_lanman_des:
            import smbpasswd
            return smbpasswd.lmhash(plaintext)
        return self.__super.encrypt_password(method, plaintext, salt=salt)


    password_bdb_regex=re.compile("^[A-Za-z0-9!#()*+,.=?@\[\]_{}~-]+$")
    password_big_regex=re.compile("[A-Z]")
    password_small_regex=re.compile("[a-z]")
    password_num_regex=re.compile("[0-9]")
    password_special_regex=re.compile("[!#()*+,.=?@\[\]_{}~-]")
    def set_password(self, plaintext):
        # Enable this after BDB is phased out:
        # From PasswordChecker...
        # self.goodenough(plaintext)

        # BDB-compatible password checking:
        if len(plaintext) != 8:
            raise PasswordGoodEnoughException("The password must be 8 characters long.")
        if not self.password_bdb_regex.match(plaintext):
            raise PasswordGoodEnoughException("Illegal character in password")
        num = (self.password_big_regex.search(plaintext) and 1 or 0) \
              + (self.password_small_regex.search(plaintext) and 1 or 0) \
              + (self.password_num_regex.search(plaintext) and 1 or 0) \
              + (self.password_special_regex.search(plaintext) and 1 or 0)
        if num < 3:
            raise PasswordGoodEnoughException("Need mix of small characters, big characters, numbers and special characters")

        # Ok, then. Acctually set the password.
        return self.__super.set_password(plaintext)

# arch-tag: 115d851e-d604-11da-80dd-29649c6d89a0
