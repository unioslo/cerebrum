#!/usr/bin/env python2.2
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
        pd['account_id'] = self.entity_id
        if(pd['posix_uid'] is None):
            pd['posix_uid'] = posix_user.get_free_uid()
        account = Account.Account(self.Cerebrum)
        account.find(self.entity_id)

        posix_user.populate(pd['posix_uid'], pd['gid'],
                            pd['gecos'], pd['home'], pd['shell'], parent=account)
        self.posix_uid = pd['posix_uid']

    def tearDown(self):
        # print "PosixUser_createTestCase.tearDown()"
        self.Cerebrum.execute(
            """DELETE FROM [:table schema=cerebrum name=posix_user]
               WHERE account_id=:id""", {'id': self.entity_id})
        super(PosixUser_createTestCase, self).tearDown()

class PosixUserTestCase(PosixUser_createTestCase):
    def testCreatePosixUser(self):
        "Test that one can create a PosixUser"
        self.failIf(getattr(self, "posix_uid", None) is None)

    def testComparePosixUser(self):
        "Check that created database posix_user object has correct values"
        posix_user = PosixUser.PosixUser(self.Cerebrum)
        posix_user.clear()
        posix_user.find(self.entity_id)
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
            posix_user.find(self.entity_id)
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

# arch-tag: ae2d5b3a-715a-4075-b551-aa607af926ab
