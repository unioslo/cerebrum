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

    def test_that_superuser_can_create_account_from_person(self):
        owner = self._get_test_testesen()
        self._assert_that_user_can_create_account(TestData.superuser_account_id, owner)

    def test_that_orakel_can_create_account_from_person(self):
        owner = self._get_test_testesen()
        self._assert_that_user_can_create_account(TestData.orakel_account_id, owner)

    def test_that_basic_can_create_account_from_person(self):
        owner = self._get_test_testesen()
        self._assert_that_user_can_create_account(TestData.basic_account_id, owner)

    def test_that_unpriveleged_can_not_create_account_from_person(self):
        owner = self._get_test_testesen()
        self._assert_that_user_can_not_create_account(TestData.unpriveleged_account_id, owner)

    def test_that_superuser_can_create_account_from_group(self):
        owner = self._get_posix_group()
        self._assert_that_user_can_create_account(TestData.superuser_account_id, owner)

    def test_that_orakel_can_create_account_from_group(self):
        owner = self._get_posix_group()
        self._assert_that_user_can_create_account(TestData.orakel_account_id, owner)

    def test_that_basic_can_not_create_account_from_group(self):
        owner = self._get_posix_group()
        self._assert_that_user_can_not_create_account(TestData.basic_account_id, owner)

    def test_that_unpriveleged_can_not_create_account_from_group(self):
        owner = self._get_posix_group()
        self._assert_that_user_can_not_create_account(TestData.unpriveleged_account_id, owner)

    def test_that_superuser_can_set_password(self):
        target = self._get_affiliated_account()
        self._assert_that_user_can_set_password(TestData.superuser_account_id, target)

    def test_that_orakel_can_set_password(self):
        target = self._get_affiliated_account()
        self._assert_that_user_can_set_password(TestData.orakel_account_id, target)

    def test_that_basic_can_not_set_password(self):
        target = self._get_affiliated_account()
        self._assert_that_user_can_not_set_password(TestData.basic_account_id, target)

    def test_that_unpriveleged_can_not_set_password(self):
        target = self._get_affiliated_account()
        self._assert_that_user_can_not_set_password(TestData.unpriveleged_account_id, target)

    def test_that_superuser_can_create_person(self):
        self._assert_that_user_can_create_person(TestData.superuser_account_id)

    def test_that_orakel_can_create_person(self):
        self._assert_that_user_can_create_person(TestData.orakel_account_id)

    def test_that_basic_can_not_create_person(self):
        self._assert_that_user_can_not_create_person(TestData.basic_account_id)

    def test_that_unpriveleged_can_create_person(self):
        self._assert_that_user_can_not_create_person(TestData.unpriveleged_account_id)

    def test_that_superuser_can_edit_affiliation(self):
        target = self._get_unaffiliated_person()
        self._assert_that_user_can_edit_affiliation(
            TestData.superuser_account_id,
            target,
            TestData.itavdeling_ou_id,
            TestData.ansatt_affiliation_id)

    def test_that_orakel_can_edit_affiliation(self):
        target = self._get_unaffiliated_person()
        self._assert_that_user_can_edit_affiliation(
            TestData.orakel_account_id,
            target,
            TestData.itavdeling_ou_id,
            TestData.ansatt_affiliation_id)

    def test_that_basic_can_edit_affiliation_of_unaffiliated_person(self):
        target = self._get_unaffiliated_person()
        self._assert_that_user_can_edit_affiliation(
            TestData.basic_account_id,
            target,
            TestData.itavdeling_ou_id,
            TestData.ansatt_affiliation_id)

    def test_that_basic_can_not_edit_affiliation_of_affiliated_person(self):
        target = self._get_affiliated_person()
        self._assert_that_user_can_not_edit_affiliation(
            TestData.basic_account_id,
            target,
            TestData.itavdeling_ou_id,
            TestData.ansatt_affiliation_id)

    def _assert_that_user_can_edit_affiliation(self, *args):
        return self._assert_is_authorized(self.auth.can_edit_affiliation, *args)

    def _assert_that_user_can_not_edit_affiliation(self, *args):
        return self._assert_is_unauthorized(self.auth.can_edit_affiliation, *args)

    def _assert_that_user_can_create_person(self, *args):
        return self._assert_is_authorized(self.auth.can_create_person, *args)

    def _assert_that_user_can_not_create_person(self, *args):
        return self._assert_is_unauthorized(self.auth.can_create_person, *args)

    def _assert_that_user_can_set_password(self, *args):
        self._assert_is_authorized(self.auth.can_set_password, *args)

    def _assert_that_user_can_not_set_password(self, *args):
        self._assert_is_unauthorized(self.auth.can_set_password, *args)

    def _assert_that_user_can_not_create_account(self, *args):
        self._assert_is_unauthorized(self.auth.can_create_account, *args)

    def _assert_that_user_can_create_account(self, *args):
        self._assert_is_authorized(self.auth.can_create_account, *args)

    def _assert_is_authorized(self, fn, *args):
        authorized = fn(*args)
        self.assertEqual(True, authorized)

    def _assert_is_unauthorized(self, fn, *args):
        authorized = fn(*args)
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

    def _get_affiliated_person(self):
        person = Person(self.db)
        person.find(TestData.affiliated_person_id)
        return person

    def _get_unaffiliated_person(self):
        person = Person(self.db)
        person.find(TestData.unaffiliated_person_id)
        return person

if __name__ == '__main__':
    unittest.main()
