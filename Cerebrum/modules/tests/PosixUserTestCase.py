#!/usr/bin/env python2.2
#
# $Id$

import unittest
from Cerebrum import Database
from Cerebrum import OU
from Cerebrum import Person
from Cerebrum import Account
from Cerebrum import Constants
from Cerebrum.modules import PosixUser

from Cerebrum.tests.AccountTestCase import Account_createTestCase

class PosixUser_createTestCase(Account_createTestCase):

    posixuser_dta = {
        'posix_uid': None,
        'gid': 999999,  # TODO: PosixUser_createTestCase should extend PosixGroup_createTestCase?
        'gecos': None,
        'home': '/home/foo',
        'shell': Account_createTestCase.co.posix_shell_bash
        }

    def setUp(self):
        super(PosixUser_createTestCase, self).setUp()
        posix_user = PosixUser.PosixUser(self.Cerebrum)
        posix_user.clear()
        self._myPopulatePosixUser(posix_user)
        
        posix_user.write_db()

    def _myPopulatePosixUser(self, posix_user):
        pd = self.posixuser_dta
        pd['account_id'] = self.account_id
        posix_user.clear()
        if(pd['posix_uid'] is None):
            pd['posix_uid'] = posix_user.get_free_uid()

        posix_user.populate(pd['account_id'], pd['posix_uid'], pd['gid'],
                            pd['gecos'], pd['home'], pd['shell'])
        self.posix_uid = pd['posix_uid'] 

    def tearDown(self):
        # print "PosixUser_createTestCase.tearDown()"
        self.Cerebrum.execute(
            """DELETE FROM [:table schema=cerebrum name=posix_user]
               WHERE account_id=:id""", {'id': self.account_id})
        super(PosixUser_createTestCase, self).tearDown()

class PosixUserTestCase(PosixUser_createTestCase):
    def testCreatePosixUser(self):
        "Test that one can create a PosixUser"
        self.failIf(getattr(self, "posix_uid", None) is None)

    def testComparePosixUser(self):
        "Check that created database posix_user object has correct values"
        posix_user = PosixUser.PosixUser(self.Cerebrum)
        posix_user.clear()
        posix_user.find(self.account_id)
        new_posix_user = PosixUser.PosixUser(self.Cerebrum)
        new_posix_user.clear()
        self._myPopulatePosixUser(new_posix_user)

        self.failIf(new_posix_user <> posix_user, "Error: should be equal")
        new_posix_user.posix_uid = 42
        self.failIf(new_posix_user == posix_user, "Error: should be different") 

    def testDeletePosixUser(self):
        "Delete the posix user"
        # This is actually a clean-up method, as we don't support deletion of PosixUsers
        old_id = self.posix_uid
        self.tearDown()
        posix_user = PosixUser.PosixUser(self.Cerebrum)
        try:
            posix_user.find(self.account_id)
            fail("Error: Should no longer exist")
        except:
            # OK
            pass

    def suite():
        suite = unittest.TestSuite()
        suite.addTest(PosixUserTestCase("testCreatePosixUser"))
        suite.addTest(PosixUserTestCase("testComparePosixUser"))
        suite.addTest(PosixUserTestCase("testDeletePosixUser"))
        return suite
    suite = staticmethod(suite)

def suite():
    """Returns a suite containing all the test cases in this module.
       It can be a good idea to put an identically named factory function
       like this in every test module. Such a naming convention allows
       automation of test discovery.
    """

    suite1 = PosixUserTestCase.suite()

    return unittest.TestSuite((suite1,))


if __name__ == '__main__':
    # When this module is executed from the command-line, run all its tests
    unittest.main(defaultTest='suite')
