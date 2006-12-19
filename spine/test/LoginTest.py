# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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
#

import unittest
from TestBase import *
from TestObjects import *

class LoginTest(SpineObjectTest):
    """Tests promote/demote of accounts and groups in Spine."""

    def createObject(self):
        self.a = DummyAccount(self.session)

    def deleteObject(self): 
        try:
            del self.a
        except: pass # It's already gone.

    def _try_login(self, username, password):
        spine2 = SpineClient.SpineClient(config=conf).connect()
        session2 = spine2.login(username, password)
        tr = session2.new_transaction()
        c = tr.get_commands()
        a = c.get_account_by_name(username)
        id = a.get_id()
        s = tr.get_cereweb_option_searcher()
        s.set_entity(a)
        s.dump()
        session2.logout()
        return id

    def testNewAccount(self):
        self.a.set_password("test")
        assert self.a.get_id() == self._try_login(self.a.get_name(), "test")

if __name__ == '__main__':
    unittest.main()

# arch-tag: c9944718-f3a0-11d9-8f80-6ca94c3e384f
