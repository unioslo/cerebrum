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
import string

import re
import cereconf
from mx import DateTime
from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum.modules import PasswordHistory
from Cerebrum.modules import Email
from Cerebrum.Utils import Factory

class AccountNMHMixin(Account.Account):
    """Account mixin class providing functionality specific to NMH.

    The methods of the core Account class that are overridden here,
    ensure that any Account objects generated through
    Cerebrum.Utils.Factory.get() provide functionality that reflects
    the policies as stated by the Indigo-project.

    """
    def register_email_contact(self, uname):
        # register "primary" e-mail address as entity_contact
        db = Factory.get('Database')()
        person = Factory.get('Person')(db)
        constants = Factory.get('Constants')(db)
        account = Factory.get('Account')(db)
        account.clear()
        try:
            account.find_by_name(uname)
        except Errors.NotFoundError:
            return False
        c_val = uname + '@nmh.uio.no'
        desc = "E-mail address exported to LDAP"
        account.add_contact_info(constants.system_override,
                                 constants.contact_email,
                                 c_val, description=desc)
        account.write_db()
        return True
        
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
