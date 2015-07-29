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
from Cerebrum.modules.pwcheck.history import PasswordHistory
from Cerebrum.modules import Email
from Cerebrum.Utils import Factory


class AccountHiNeMixin(Account.Account):
    """Account mixin class providing functionality specific to HiNE.

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
        # register "primary" e-mail address as entity_contact
        c_val = name + '@' + cereconf.EMAIL_DEFAULT_DOMAIN
        desc = "E-mail address exported to LDAP"
        self.populate_contact_info(self.const.system_cached,
                                   type=self.const.contact_email,
                                   value=c_val, description=desc)

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
            if len(passwd) >= 15 and len(pwd) > 1:
                # do not generate passwords longer than 20 chars
                if len(passwd) <= 20:
                    return passwd
                else:
                    pwd.pop(0)
                    
    def illegal_name(self, name):
        """HiNe can only allow max 8 characters in usernames, due to
        restrictions in e.g. TimeEdit.

        """
        if len(name) > 8:
            return "too long (%s); max 8 chars allowed" % name
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
            ph = PasswordHistory(self._db)
            ph.add_history(self, plain)
        return ret

class AccountHiNeEmailMixin(Account.Account):
    def get_primary_mailaddress(self):
        primary = self.get_contact_info(type=self.const.contact_email)
        if primary:
            return primary[0]['contact_value']
        else:
            return "<ukjent>"
