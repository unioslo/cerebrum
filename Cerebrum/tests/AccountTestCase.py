#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2002, 2003 University of Oslo, Norway
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

import unittest
import cereconf
from Cerebrum import Database
from Cerebrum import Errors
from Cerebrum import OU
from Cerebrum import Person
from Cerebrum import Account
from Cerebrum import Constants

from Cerebrum.tests.PersonTestCase import Person_createTestCase


class Account_createTestCase(Person_createTestCase):

    account_dta = {
        'name': 'name',
        'owner_type': Person_createTestCase.co.entity_person,
        'owner_id': None,               # Set during setUp
        'np_type' : None,
        'creator_id': None,
        'expire_date': None
        }

    def setUp(self):
        super(Account_createTestCase, self).setUp()
        account = Account.Account(self.Cerebrum)
        self._myPopulateAccount(account)
        account.write_db()
        self.account_id = account.entity_id
        self.account = account

    def _myPopulateAccount(self, account):
        ad = self.account_dta
        if ad.get('owner_id', None) is None:
            ad['owner_id'] = self.person_id
        if ad.get('creator_id', None) is None:
            account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
            ad['creator_id'] = account.entity_id
            account.clear()
        account.populate(ad['name'], ad['owner_type'], ad['owner_id'],
                         ad['np_type'], ad['creator_id'], ad['expire_date'])

    def tearDown(self):
        # print "Account_createTestCase.tearDown()"
        self.Cerebrum.execute("""
        DELETE FROM [:table schema=cerebrum name=entity_name]
        WHERE entity_id=:id""", {'id': self.account_id})
        self.Cerebrum.execute("""
        DELETE FROM [:table schema=cerebrum name=account_info]
        WHERE account_id=:id""", {'id': self.account_id})
        super(Account_createTestCase, self).tearDown()


class AccountTestCase(Account_createTestCase):

    def testCreateAccount(self):
        "Test that one can create an Account"
        self.failIf(not hasattr(self, "account_id"))

    def testCompareAccount(self):
        "Check that created database Account object has correct values"
        account = Account.Account(self.Cerebrum)
        account.find(self.account_id)
        new_account = Account.Account(self.Cerebrum)
        self._myPopulateAccount(new_account)
        self.failIf(new_account <> account, "Error: should be equal")
        new_account.account_name = 'foobar'
        self.failIf(new_account == account, "Error: should be different")

    def testDeleteAccount(self):
        "Delete the Account"
        # This is actually a clean-up method, as we don't support
        # deletion of Accounts.
        self.tearDown()
        account = Account.Account(self.Cerebrum)
        self.assertRaises(Errors.NotFoundError, account.find, self.account_id)

    def suite():
        suite = unittest.TestSuite()
        suite.addTest(AccountTestCase("testCreateAccount"))
        suite.addTest(AccountTestCase("testCompareAccount"))
        suite.addTest(AccountTestCase("testDeleteAccount"))
        return suite
    suite = staticmethod(suite)


def suite():
    """Returns a suite containing all the test cases in this module.

    It can be a good idea to put an identically named factory function
    like this in every test module. Such a naming convention allows
    automation of test discovery.

    """

    suite1 = AccountTestCase.suite()
    return unittest.TestSuite((suite1,))


if __name__ == '__main__':
    # When executed as a script, perform all tests in suite().
    unittest.main(defaultTest='suite')

# arch-tag: 9c91b409-4a4c-4a9c-b80a-cea6c9056604
