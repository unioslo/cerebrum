#!/usr/bin/env python2.2
#
# $Id$

import unittest
from Cerebrum import Database
from Cerebrum import OU
from Cerebrum import Person
from Cerebrum import Account
from Cerebrum import Constants

from Cerebrum.tests.PersonTestCase import Person_createTestCase

class Account_createTestCase(Person_createTestCase):

    account_dta = {
        'name': 'name',
        'owner_type': Person_createTestCase.co.entity_person,
        'owner_id': None,  # Set during setUp
        'np_type' : None,
        'creator_id': 888888,
        'expire_date': None
        }

    def setUp(self):
        super(Account_createTestCase, self).setUp()

        account = Account.Account(self.Cerebrum)
        account.clear()
        self._myPopulateAccount(account)
        
        account.write_db()
        self.account_id = account.account_id

    def _myPopulateAccount(self, account):
        ad = self.account_dta
        ad['owner_id'] = self.person_id
        account.clear()
        Account.Account.populate(account, ad['name'], ad['owner_type'], ad['owner_id'], ad['np_type'],
                         ad['creator_id'], ad['expire_date'])

    def tearDown(self):
        # print "Account_createTestCase.tearDown()"
        self.Cerebrum.execute(
            """DELETE FROM [:table schema=cerebrum name=entity_name]
               WHERE entity_id=:id""", {'id': self.account_id})
        self.Cerebrum.execute(
            """DELETE FROM [:table schema=cerebrum name=account_info]
               WHERE account_id=:id""", {'id': self.account_id})
        super(Person_createTestCase, self).tearDown()


class AccountTestCase(Account_createTestCase):
    def testCreateAccount(self):
        "Test that one can create an Account"
        self.failIf(getattr(self, "account_id", None) is None)

    def testCompareAccount(self):
        "Check that created database object has correct values"
        account = Account.Account(self.Cerebrum)
        account.clear()
        account.find(self.account_id)
        new_account = Account.Account(self.Cerebrum)
        new_account.clear()
        self._myPopulateAccount(new_account)

        self.failIf(new_account <> account, "Error: should be equal")
        new_account.account_name = 'foobar'
        self.failIf(new_account == account, "Error: should be different") 

    def testDeleteAccount(self):
        "Delete the person"
        # This is actually a clean-up method, as we don't support deletion of Persons
        old_id = self.account_id
        self.tearDown()
        account = Account.Account(self.Cerebrum)
        try:
            account.find(self.account_id)
            fail("Error: Should no longer exist")
        except:
            # OK
            pass

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
    # When this module is executed from the command-line, run all its tests
    unittest.main(defaultTest='suite')
