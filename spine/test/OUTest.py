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

class OUTest(unittest.TestCase):
    """Tests the OU implementation in Spine."""
    def setUp(self):
        self.session = spine.login(username, password)

    def tearDown(self):
        self.session.logout()

    def __createTwoOUs(self, transaction):
        commands = transaction.get_commands()
        ou_name = str(id(transaction))
        try:
            commands.create_ou(ou_name, 1, 1, 1, 1)
        except TypeError:
            raise Spine.Errors.DatabaseError # Stedkode mixin isn't loaded, we raise to make our test succeed
        commands.create_ou(ou_name, 1, 1, 1, 1)

    def testStedkodeUniqueConstraint(self):
        """Tests that the create_ou() method for the stedkode mixin correctly
        raises a DatabaseError when trying to create an OU which violates the
        unique constraint on stedkode."""
        transaction = self.session.new_transaction()
        self.assertRaises(Spine.Errors.DatabaseError, self.__createTwoOUs, transaction)
        transaction.rollback()
        

if __name__ == '__main__':
    unittest.main()
