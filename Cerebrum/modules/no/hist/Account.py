# -*- coding: iso-8859-1 -*-
# Copyright 2004 University of Oslo, Norway
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

class AccountHiSTMixin(Account.Account):
    """Delete an account, most db-references must be removed before calling this""" 
    def delete(self):
        for s in self.get_account_types():
          self.del_account_type(s['ou_id'], s['affiliation'])
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=account_authentication]
        WHERE account_id=:acc_id""", {'acc_id' : self.entity_id})
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=account_info]
        WHERE account_id=:acc_id""", {'acc_id' : self.entity_id})
        self.__super.delete()

# arch-tag: 0742389f-b5a4-4c58-96b4-f40659a92b8a
