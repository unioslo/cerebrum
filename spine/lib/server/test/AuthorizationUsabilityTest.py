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

from unittest import TestCase, main
from MockDB import *
from pmock import Mock

import sys
sys.path.append("..")
import Authorization
import TestData

class UserTest(TestCase):
    def setUp(self):
        # Initialize the mockdatabase with permissiondata.
        self.db = MockDB(TestData.operation_sets)
        self.ac = self.db._add_account(TestData.accounts['user'])
        self.ao = Authorization.Authorization(self.ac, database=self.db)

    def testChangePassword(self):
        self.assertTrue(self.ao.has_permission(self.ac, 'set_password'))

if __name__ == '__main__':
    main()
