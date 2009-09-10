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

import cerebrum_path
from Cerebrum import Utils
from Cerebrum.modules.bofhd.errors import PermissionDenied
from Cerebrum.modules.no.ntnu.bofhd_auth import BofhdAuth

import TestData

Database = Utils.Factory.get("Database")
Person = Utils.Factory.get("Person")
Account = Utils.Factory.get("Account")
Group = Utils.Factory.get("Group")

class AuthTest(unittest.TestCase):
    def setUp(self, *args, **kwargs):
        super(AuthTest, self).setUp(*args, **kwargs)
        self.db = Database()
        self.auth = BofhdAuth(self.db)

    def test_that_superuser_can_create_person_account(self):
        owner = self._get_test_testesen()
        self._assert_can_create_account(TestData.superuser_account_id, owner)

    def test_that_orakel_can_create_person_account_using_global_access(self):
        owner = self._get_test_testesen()
        self._assert_can_create_account(TestData.orakel_account_id, owner)

    def test_that_basic_can_create_person_account_without_global_access(self):
        owner = self._get_test_testesen()
        self._assert_can_create_account(TestData.basic_account_id, owner)

    def test_that_unpriveleged_can_not_create_person_account(self):
        owner = self._get_test_testesen()
        self._assert_can_not_create_account(TestData.unpriveleged_account_id, owner)

    def test_that_superuser_can_create_group_account(self):
        owner = self._get_posix_group()
        self._assert_can_create_account(TestData.superuser_account_id, owner)

    def test_that_orakel_can_create_group_account_using_global_access(self):
        owner = self._get_posix_group()
        self._assert_can_create_account(TestData.orakel_account_id, owner)

    def test_that_basic_can_not_create_group_account_without_global_access(self):
        owner = self._get_posix_group()
        self._assert_can_not_create_account(TestData.basic_account_id, owner)

    def test_that_unpriveleged_can_not_create_group_account(self):
        owner = self._get_posix_group()
        self._assert_can_not_create_account(TestData.unpriveleged_account_id, owner)

    def test_that_superuser_can_set_password(self):
        target = self._get_affiliated_account()
        self._assert_can_set_password(TestData.superuser_account_id, target)

    def test_that_orakel_can_set_password(self):
        target = self._get_affiliated_account()
        self._assert_can_set_password(TestData.orakel_account_id, target)

    def test_that_basic_can_not_set_password(self):
        target = self._get_affiliated_account()
        self._assert_can_not_set_password(TestData.basic_account_id, target)

    def test_that_unpriveleged_can_not_set_password(self):
        target = self._get_affiliated_account()
        self._assert_can_not_set_password(TestData.unpriveleged_account_id, target)

    def _assert_can_set_password(self, operator_id, target):
        self._assert_is_authorized(
            self.auth.can_set_password,
            operator_id,
            target)

    def _assert_can_not_set_password(self, operator_id, target):
        self._assert_is_unauthorized(
            self.auth.can_set_password,
            operator_id,
            target)

    def _assert_can_not_create_account(self, operator_id, owner):
        self._assert_is_unauthorized(
            self.auth.can_create_account,
            operator_id,
            owner)

    def _assert_can_create_account(self, operator_id, owner, expected=True):
        self._assert_is_authorized(
            self.auth.can_create_account,
            operator_id,
            owner)

    def _assert_is_authorized(self, fn, *args, **kwargs):
        authorized = fn(*args, **kwargs)
        self.assertEqual(True, authorized)

    def _assert_is_unauthorized(self, fn, *args, **kwargs):
        authorized = fn(*args, **kwargs)
        self.assertEqual(False, authorized)

    def _get_posix_group(self):
        owner = Group(self.db)
        owner.find(TestData.posix_group_id)
        return owner

    def _get_test_testesen(self):
        owner = Person(self.db)
        owner.find(TestData.test_testesen_id)
        return owner

    def _get_affiliated_account(self):
        account = Account(self.db)
        account.find(TestData.affiliated_account_id)
        return account

if __name__ == '__main__':
    unittest.main()
