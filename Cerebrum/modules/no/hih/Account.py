# -*- coding: iso-8859-1 -*-
# Copyright 2010 University of Oslo, Norway
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

import re
import random
import string
import time
import pickle

import cereconf

from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum.modules import PasswordHistory
from Cerebrum.Utils import Factory


class AccountHiHMixin(Account.Account):
    """Account mixin class providing functionality specific to HiH.

    The methods of the core Account class that are overridden here,
    ensure that any Account objects generated through
    Cerebrum.Utils.Factory.get() provide functionality that reflects
    the policies as stated by the Indigo-project.

    """
    def populate(self, name, owner_type, owner_id, np_type, creator_id,
                 expire_date, parent=None):
        if parent is not None:
            self.__xerox__(parent)
        # Override Account.populate in order to register 'primary e-mail
        # address
        self.__super.populate(name, owner_type, owner_id, np_type, creator_id,
                              expire_date)


    def suggest_unames(self, domain, fname, lname, maxlen=8, suffix=""):
        # Override Account.suggest_unames as HiHH allows up to 10 chars
        # in unames
        return self.__super.suggest_unames(domain, fname, lname, maxlen=10)
    
    def make_passwd(self, uname):
        words = []
        pwd = []
        passwd = ""
        for fname in cereconf.PASSPHRASE_DICTIONARIES:
            f = file(fname, 'r')
            for l in f:
                words.append(l.rstrip())
            while(1):
                pwd.append(words[random.randint(0, len(words)-1)])
                passwd = ' '.join([a for a in pwd])
                if len(passwd) >= 12 and len(pwd) > 1:
                    if len(passwd) <= 20:
                        return passwd
                else:
                    pwd.pop(0)
                                                                                                                                                

    def illegal_name(self, name):
        """HiH can only allow max 10 characters in usernames, due to
        restrictions in e.g. TimeEdit.

        """
        if len(name) > 10:
            return "too long (%s); max 10 chars allowed" % name
        # TBD: How do these mix with student account automation?
        # ... and migration? Disable for now.
        #if re.search("[^a-z]", name):
        #    return "contains illegal characters (%s); only a-z allowed" % name
        #if re.search("^\d{6}$", name):
        #    return "disallowed due to possible conflict with FS-based usernames" % name
                
        return False


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

