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

import os, sys, traceback
from pmock import *
from unittest import TestCase
import unittest

sys.path.append("..")

import Authorization
from Cerebrum.spine.Account import Account
from Cerebrum.spine.Types import CodeType

class SuperUserTest(TestCase):
    """
    Test that the superuser can do everything.
    """

    def setUp(self):
        a = Mock()
        a.expects(at_least_once()).get_id().will(return_value(2))
        a.expects(at_least_once()).is_superuser().will(return_value(True))

        self.account = a

    def test(self):
        """Make sure the testsystem works."""
        pass
        

    def testMockAccount(self):
        """Make sure the mock account behaves properly."""
        self.assertTrue(self.account.get_id() == 2)
        self.assertTrue(self.account.is_superuser())
        self.account.verify()

    def testCheckPermission(self):
        """Permission check on a superuser is done first, so the arguments
           for the check_permission call doesn't matter."""
        auth_obj = Authorization.Authorization(self.account)
        self.assertTrue(auth_obj.check_permission(None, None))
        self.account.verify()

class UserTest(TestCase):
    """
    Test that a regular user can do some stuff, but not all.
    """

    def setUp(self):
        self.userid = 120
        a = Mock()
        a.expects(at_least_once()).get_id().will(return_value(self.userid))
        a.expects(at_least_once()).is_superuser().will(return_value(False))
        self.auth_obj = Authorization.Authorization(a)
        self.account = a

    def tearDown(self):
        self.account.verify()

    def testPublicMethod(self):
        """Some methods are considered public and should always return True"""
        class T(object):
            def pm(self):
                pass
            pm.signature_public = True
        obj = T()

        self.assertTrue(self.auth_obj.check_permission(obj, 'pm'))

    def testPublicObject(self):
        """Some objects are considered public and should always return True"""
        class T(object):
            def pm(self):
                pass
        T.signature_public = True
        obj = T()

        self.assertTrue(self.auth_obj.check_permission(obj, 'pm'))

    def testPrivateMethod(self):
        """Some methods are considered private even if their objects are public"""
        class T(object):
            def pm(self):
                pass
            pm.signature_public = False
        T.signature_public = True

        obj = T()

        self.assertFalse(self.auth_obj.check_permission(obj, 'pm'))

    def testCodeValue(self):
        """Methods on objects that are derived from CodeType are public"""
        class Phony(object):
            def getClass(self):
                return CodeType
            def pm(self):
                pass
            __class__ = property(getClass)

        obj = Phony()
        self.assertTrue(self.auth_obj.check_permission(obj, 'pm'))

    def testSetOwnPassword(self):
        """A user should be able to set his/her own password."""
        class PhonyAccount(Mock):
            def getClass(self):
                return Account
            __class__ = property(getClass)
        account = PhonyAccount()
        account.expects(once()).get_id().will(return_value(self.userid))
        self.assertTrue(self.auth_obj.check_permission(account, 'set_password'))

    def testSetOtherPassword(self):
        """A user should not be able to set someone elses password."""
        class PhonyAccount(Mock):
            def getClass(self):
                return Account
            __class__ = property(getClass)
        account = PhonyAccount()
        account.expects(once()).get_id().will(return_value(self.userid + 1))
        self.assertFalse(self.auth_obj.check_permission(account, 'set_password'))

    # TODO: Test more.

if __name__ == '__main__':
    unittest.main()
