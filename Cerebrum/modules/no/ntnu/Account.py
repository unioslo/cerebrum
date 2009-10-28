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
import cereconf

# Todo: create a local module to store these rules.

posix_spreads=(
    "user@ansatt",
    "user@stud"
    )

spread_homedirs = cereconf.SPREAD_HOMEDIRS


account_name_regex=re.compile("^[a-z][a-z0-9]*$")
account_name_np_regex=re.compile("^[a-z][a-z0-9._-]*$")


class AccountNTNUMixin(Account.Account):
    def illegal_name(self, name):
        maxlen=8
        regex=account_name_regex
        # Allow weird usernames for non-personal accounts.
        # XXX only works when self refers to the account!
        if self.np_type:
            maxlen=64
            regex=account_name_np_regex
        if len(name) > maxlen:
            return "too long (%s)" % name
        if not regex.match(name):
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
        if (1 # str(self.const.Spread(spread)) in posix_spreads
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
        avail_disks = [d for d in all_disks if d[2]]
        diskpath,ulen,weight = random.choice(avail_disks)
        home = None
        if ulen:
            home = self.account_name[:ulen] + "/" + self.account_name
        disk = Factory.get('Disk')(self._db)
        disk.find_by_path(diskpath)
        homedir = self.set_homedir(disk_id=disk.entity_id, home=home,
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
        """
        Overloaded to support lanman_des, since radius uses this dinosaur.
        """
        if method == self.const.auth_type_lanman_des:
            import smbpasswd
            return smbpasswd.lmhash(plaintext)
        return self.__super.encrypt_password(method, plaintext, salt=salt)

    def verify_password(self, method, plaintext, cryptstring):
        """
        Overloaded to support lanman_des, since radius uses this dinosaur.
        """
        if method == self.const.auth_type_lanman_des:
            s = self.encrypt_password(method, plaintext, salt=cryptstring)
            return (s == cryptstring)
        return self.__super.verify_password(method, plaintext, cryptstring)

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


    # Hacked version of AutoPriorityMixin to remain compatible with
    # BDB's idea of primary accounts (saved in the trait). LDAP needs this.
    # Keep while BDB is still running.
    def _calculate_account_priority(self, ou_id, affiliation,
                                    current_pri=None):
        # Determine the status this affiliation resolves to
        if self.owner_id is None:
            raise ValueError, "non-owned account can't have account_type"
        person = Factory.get('Person')(self._db)
        status = None
        for row in person.list_affiliations(person_id=self.owner_id,
                                            include_deleted=True):
            if row['ou_id'] == ou_id and row['affiliation'] == affiliation:
                status = self.const.PersonAffStatus(
                    row['status'])._get_status()
                break
        if status is None:
            raise ValueError, "Person don't have that affiliation"
        affiliationstr = str(self.const.PersonAffiliation(int(affiliation)))

        # Find the range that we resolve to
        pri_ranges = cereconf.ACCOUNT_PRIORITY_RANGES
        if not isinstance(pri_ranges, dict):
            return None
        if not affiliationstr in pri_ranges:
            affiliationstr = '*'
        if not status in pri_ranges[affiliationstr]:
            status = '*'
        pri_min, pri_max = pri_ranges[affiliationstr][status]

        person.find(self.owner_id)
        primary_trait = person.get_trait(self.const.trait_primary_account)
        if primary_trait is not None:
            primary_account = primary_trait['target_id']
            isprimary = (primary_account == self.entity_id)
        else:
            isprimary = False
        
        if not isprimary and pri_min <= current_pri < pri_max:
            return current_pri
        
        # Find taken values in this range and sort them
        taken = []
        thisaff = []
        for row in self.get_account_types(all_persons_types=True,
                                          filter_expired=False):
            taken.append(int(row['priority']))
            if row['ou_id'] == ou_id and row['affiliation'] == affiliation:
                thisaff.append(int(row['priority']))
        taken = [x for x in taken if x >= pri_min and x < pri_max]
        taken.sort()
        thisaff.sort()
        

        if isprimary and len(thisaff) > 0:
            # Keep if this account already has the lowest pri
            if (current_pri == thisaff[0] and
                pri_min <= current_pri < pri_max):
                return current_pri
            # Try to lower the priority
            new_pri = thisaff[0] - 1
        else:
            if (not taken):
                taken.append(pri_min)
            new_pri = taken[-1] + 2
            if new_pri < pri_max:
                return new_pri

            # In the unlikely event that the previous taken value was at the
            # end of the range
            new_pri = pri_max - 1
        while new_pri >= pri_min:
            if new_pri not in taken:
                return new_pri
            new_pri -= 1
        raise ValueError, "No free priorities for that account_type!"




# arch-tag: 115d851e-d604-11da-80dd-29649c6d89a0
