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
from omniORB import CORBA

class HomeDirectoryTest(unittest.TestCase):
    """Test homedirectory and accounthome in spine."""

    def setUp(self):
        self.session = spine.login(username, password)

    def tearDown(self):
        self.session.logout()

    def __create_person(self, transaction):
        commands = transaction.get_commands()
        date = commands.get_date_now()
        gender = transaction.get_gender_type('M')
        source = transaction.get_source_system('Manual')
        name = 'unittest%s' % id(self)
        return commands.create_person(date, gender, name, source)

    def __create_account(self, tr):
        owner = self.__create_person(tr)
        date = tr.get_commands().get_date_none()
        name = 'unittest_ac%s' % id(self)
        account = tr.get_commands().create_account(name, owner, date)

        searcher = tr.get_spread_searcher()
        searcher.set_entity_type(account.get_type())
        spread = searcher.search()[0]
        account.add_spread(spread)
        
        return account, name

    def __create_disk_with_host(self, tr):
        host_name = 'unittest_h%s' % id(self)
        disk_path = 'unittest_d%s' % id(self)
        host = tr.get_commands().create_host(host_name, host_name)
        disk = tr.get_commands().create_disk(host, disk_path, disk_path)
        return disk, disk_path
        
    def testSetHomedir(self):
        tr = self.session.new_transaction()
        account, a_name = self.__create_account(tr)
        disk, path = self.__create_disk_with_host(tr)
        
        assert a_name == account.get_name()
        assert path == disk.get_path()
    
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
        
        tr.rollback()

    def testRemoveHomedir(self):
        tr = self.session.new_transaction()
        account, a_name = self.__create_account(tr)
        
        home = "localhost:/home/www"
        spread = account.get_spreads()[0]
        account.set_homedir(spread, home, None)
        
        assert home == account.get_homedir(spread).get_home()

        account.remove_homedir(spread)

        self.assertRaises(Spine.Errors.NotFoundError,
                          account.get_homedir, spread)

        tr.rollback()
        
    def testGetHomes(self):
        tr = self.session.new_transaction()
        account, a_name = self.__create_account(tr)
        
        home = "localhost:/home/www"
        spread = account.get_spreads()[0]
        account.set_homedir(spread, home, None)
        
        assert home == account.get_homedir(spread).get_home()
        assert home == account.get_homes()[0].get_homedir().get_home()
        assert spread.get_id() == account.get_homes()[0].get_spread().get_id()

        account.remove_homedir(spread)

        assert account.get_homes() == []
        
        tr.rollback()
        
if __name__ == '__main__':
    unittest.main()

