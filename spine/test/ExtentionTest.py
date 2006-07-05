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
#

import unittest
from TestBase import *
from omniORB import CORBA

class ExtentionTest(unittest.TestCase):
    """Tests Spine extention interface"""
    def setUp(self):
        self.session = spine.login(username, password)

    def tearDown(self):
        self.session.logout()

    def testGetExtentions(self):
        tr = self.session.new_transaction()
    	cmd = tr.get_commands()
	exts = cmd.get_extentions()
	assert "posixuser" in exts
        tr.rollback()

    def testHasExtention(self):
        tr = self.session.new_transaction()
        cmd = tr.get_commands()
        assert cmd.has_extention("posixuser")
	assert not cmd.has_extention("")
	assert not cmd.has_extention("nosuchextention")
        tr.rollback()
    
if __name__ == '__main__':
    unittest.main()

# arch-tag: c9944718-f3a0-11d9-8f80-6ca94c3e384f
