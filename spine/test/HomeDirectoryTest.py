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
from omniORB import CORBA
import SpineIDL

class HomeDirectoryTest(unittest.TestCase):
    """Test homedirectory and accounthome in spine."""

    def setUp(self):
        self.session = spine.login(username, password)

    def tearDown(self):
        self.session.logout()

    def testSetHomedir(self):
        _account = DummyAccount(self.session)
        _account._add_spread()
        _disk = DummyDisk(self.session)
        tr = self.session.new_transaction()
        account = _account._get_obj(tr)
        disk = _disk._get_obj(tr)
        
        home = "localhost:/home/www"
        spread = account.get_spreads()[0]
        account.set_homedir(spread, home, None)

        assert home == account.get_homedir(spread).get_home()
        assert home == account.get_homedir(spread).get_path()

        account.set_homedir(spread, "", disk)
        
        assert "" == account.get_homedir(spread).get_home()
        assert home != account.get_homedir(spread).get_path()
        assert (disk.get_path() == 
                account.get_homedir(spread).get_disk().get_path())
        tr.commit()

    def testRemoveHomedir(self):
        _account = DummyAccount(self.session)
        _account._add_spread()
        account = _account._get_obj()
        
        home = "localhost:/home/www"
        spread = account.get_spreads()[0]
        account.set_homedir(spread, home, None)
        
        assert home == account.get_homedir(spread).get_home()

        account.remove_homedir(spread)

        self.assertRaises(SpineIDL.Errors.NotFoundError,
                          account.get_homedir, spread)

        
    def testGetHomes(self):
        _account = DummyAccount(self.session)
        _account._add_spread()
        account = _account._get_obj()
        
        home = "localhost:/home/www"
        spread = account.get_spreads()[0]
        account.set_homedir(spread, home, None)
        
        assert home == account.get_homedir(spread).get_home()
        assert home == account.get_homes()[0].get_homedir().get_home()
        assert spread.get_id() == account.get_homes()[0].get_spread().get_id()

        account.remove_homedir(spread)

        assert account.get_homes() == []
        
if __name__ == '__main__':
    unittest.main()

# arch-tag: 0e056fe6-00a6-11da-8066-8182e2884fde
