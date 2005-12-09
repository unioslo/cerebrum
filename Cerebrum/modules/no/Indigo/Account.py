# -*- coding: iso-8859-1 -*-
# Copyright 2003-2005 University of Oslo, Norway
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

""""""

import random

import re
import cereconf
from mx import DateTime
from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum.modules import Email
from Cerebrum.modules import PasswordHistory

class AccountIndigoMixin(Account.Account):
    """Account mixin class providing functionality specific to Indigo.

    The methods of the core Account class that are overridden here,
    ensure that any Account objects generated through
    Cerebrum.Utils.Factory.get() provide functionality that reflects
    the policies as stated by the Indigo-project.

    """
    def make_passwd(self, uname):
        pot = string.ascii_letters + string.digits
        count = 0
        pwd = []
        if self.is_employee():
            self.__super.make_password(uname)
        else:
            while count < 2:
                pwd.append(string.digits[random.randint(0, len(string.digits)-1)])
                count += 1
            while count < 8:
                pwd.append(string.ascii_letters[random.randint(0, len(string.ascii_letters)-1)])
                count += 1
            random.shuffle(pwd)
            return string.join(pwd,'')


    def set_password(self, plaintext):
        # Override Account.set_password so that we get a copy of the
        # plaintext password
        self.__plaintext_password = plaintext
        self.__super.set_password(plaintext)

    def write_db(self):
        try:
            plain = self.__plaintext_password
        except AttributeError:
            plain = None
        ret = self.__super.write_db()
        if plain is not None:
            ph = PasswordHistory.PasswordHistory(self._db)
            ph.add_history(self, plain)
        return ret

    def is_employee(self):
        for r in self.get_account_types():
            if r['affiliation'] == self.const.affiliation_ansatt:
                return True
        return False

    def enc_auth_type_pgp_crypt(self, plaintext, salt=None):
        return pgp_encrypt(plaintext, cereconf.PGPID)

    
