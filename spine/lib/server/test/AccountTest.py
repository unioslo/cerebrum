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
import TestData

from Cerebrum.spine.Account import Account

class AccountTest(TestCase):
    def setUp(self):
        self.db = MockDB()
        self.ac_dict = TestData.accounts['user']
        self.id = self.ac_dict['id']
        self.db._add_account(self.ac_dict)
        self.ac = Account(self.db, self.id)

    def test_setUp_and_tearDown(self):
        pass

    def test_get_id(self):
        assert self.id == self.ac.get_id()

    def test_value_domain(self):
        # self.ac._get_sql forces ValueDomainHack to be run
        self.ac._get_sql()

    def test_get_name(self):
        assert self.ac.get_name() == 'testuser'

    def test_is_superuser(self):
        self.assertFalse(self.ac.is_superuser())

if __name__ == '__main__':
    main()
