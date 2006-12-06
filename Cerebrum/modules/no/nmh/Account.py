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

""""""


import cereconf

from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum.modules import PasswordHistory
from Cerebrum.Utils import Factory

class AccountNMHMixin(Account.Account):
    """Account mixin class providing functionality specific to NMH.

    The methods of the core Account class that are overridden here,
    ensure that any Account objects generated through
    Cerebrum.Utils.Factory.get() provide functionality that reflects
    the policies as stated by the Indigo-project.

    """
    def populate(self, name, owner_type, owner_id, np_type, creator_id,
                 expire_date):
        self.__super.populate(name, owner_type, owner_id, np_type, creator_id,
                              expire_date)
        # register "primary" e-mail address as entity_contact
        c_val = name + '@nmh.uio.no'
        desc = "E-mail address exported to LDAP"
        self.populate_contact_info(self.const.system_cached,
                                   type=self.const.contact_email,
                                   value=c_val, description=desc)

        
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
