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

import sys
from unittest import TestCase, main
from pmock import *

from Cerebrum.modules.bofhd.auth import BofhdAuth, BofhdAuthRole, BofhdAuthOpSet
from Cerebrum.modules.bofhd.utils import _AuthRoleOpCode as AuthRoleOpCode
from Cerebrum.Utils import Factory

from Cerebrum.spine.Types import CodeType

from MockDB import *

sys.path.append("..")
import Authorization

class MockDBTestCase(TestCase):
    def setUp(self):
        self.db = MockDB()

    def tearDown(self):
        self.db.verify()

class TestMockDB(MockDBTestCase):
    def testBofhdAuth_setup(self):
        self.db._init_bofhdauth()
        BofhdAuth(self.db)

    def testSeq_increments(self):
        self.db._init_seq()

        self.assertEquals(1000, self.db.nextval('entity_id_seq'))
        self.assertEquals(1001, self.db.nextval('entity_id_seq'))
        self.assertEquals(1002, self.db.nextval('entity_id_seq'))

    def testSeq_uninitialized(self):
        try:
            self.db.nextval('test_seq')
            self.fail(), "Didn't raise exception."
        except TypeError:
            pass

class AuthorizationTest(MockDBTestCase):
    def setUp(self):
        super(AuthorizationTest, self).setUp()
        self.userid = 120 # The userID for our regular user.
        self.ownerid = 119 # The owner of our regular user.
        self.account = self.db._get_user(self.userid, self.ownerid)

        self.auth_obj = Authorization.Authorization(self.account, database=self.db)

    def tearDown(self):
        super(AuthorizationTest, self).tearDown()

class BofhdAuthTest(AuthorizationTest):
    def setUp(self):
        super(BofhdAuthTest, self).setUp()
        self.db._init_bofhdauth()
        self.ba = BofhdAuth(self.db)

    def testSuperUser_member_of_bootstrap_group(self):
        self.db._superuser(self.userid)
        self.assertTrue(self.auth_obj.is_superuser(self.ba))

    def testSuperUser_not_superuser(self):
        self.db._superuser(None)
        self.assertFalse(self.auth_obj.is_superuser(self.ba))

    def testSetOtherPassword(self):
        """A user should not be able to set someone elses password."""
        target = self.db._getAccount(self.userid + 1)
        operation = 'Account.set_password'

        self.assertFalse(self.auth_obj.has_user_access(operation, target))

    def testSetOwnPassword(self):
        """A user should be able to set his/her own password."""
        target = self.db._getAccount(self.userid)
        operation = 'Account.set_password'
        self.db._add_opset('own_account', [operation])
        op = self.db._get_op(operation)

        self.assertTrue(self.auth_obj.has_user_access(op, target))

    def testChangeOwnPerson(self):
        operation = 'Person.set_display_name'
        self.db._add_opset('own_account', [operation])

        self.auth_obj.has_user_access(operation, self.account)

    def testHasAccess(self):
        target_id = self.userid + 10
        op_name = 'Account.set_password'
        self.db._add_opset('orakel', [op_name])
        self.op = self.db._get_op(op_name)
        self.db._add_op_role(self.userid, 'orakel', target_id, self.db._stub)
        self.db._add_group_member(self.userid) # Stubs out group stuff.
        self.db._grant_access_to_entity_via_ou((self.userid,), hash(op_name), target_id)
        target = self.db._getAccount(target_id)

        self.assertTrue(self.auth_obj.has_access(self.op, target, self.ba))

    def testHasAccessThroughGroup(self):
        group_id = self.userid + 5
        target_id = self.userid + 10
        op_name = 'Account.set_password'
        self.db._add_opset('orakel', [op_name])
        self.op = self.db._get_op(op_name)
        self.db._add_group_member(group_id, self.userid)
        self.db._add_op_role(group_id, 'orakel', target_id, self.db._stub)
        target = self.db._getAccount(target_id)
        self.db._grant_access_to_entity_via_ou((self.userid, group_id), hash(op_name), target_id)
        self.assertTrue(self.auth_obj.has_access(self.op, target, self.ba))

class NonBofhdAuthTest(AuthorizationTest):
    """Tests that do not depend on the contents of the database."""
    def setUp(self):
        super(NonBofhdAuthTest, self).setUp()
        self.db._init_bofhdauth(method=self.db._stub)
        self.db._no_superuser(method=self.db._stub)
        self.db._add_op_role(None, method=self.db._stub)
        self.obj = Mock()
        self.obj.pm = lambda x: x

    def tearDown(self):
        super(NonBofhdAuthTest, self).tearDown()

    def testPublicMethod(self):
        """Methods that have the signature_public attr set to True should
        always return true."""
        self.obj.pm.signature_public = True
        self.assertTrue(self.auth_obj.is_public(self.obj.__class__,
                                                self.obj, self.obj.pm))

    def testPublicObject(self):
        """Objects that have the signature_public attr set to True should
        return true."""
        self.obj.signature_public = True

        self.assertTrue(self.auth_obj.is_public(self.obj.__class__,
                                                self.obj, self.obj.pm))

    def testPrivateMethod(self):
        """Methods that have the signature_public attr set to False should
        ignore the objects signature_public attr."""
        self.obj.signature_public = True
        self.obj.pm.signature_public = False

        self.assertFalse(self.auth_obj.is_public(self.obj.__class__,
                                                self.obj, self.obj.pm))

    def testCodeValue(self):
        """Methods on objects that are derived from CodeType are public"""
        self.obj.__class__ = CodeType
        self.obj.pm

        self.assertTrue(self.auth_obj.is_public(self.obj.__class__,
                                                self.obj, self.obj.pm))

class HasCommandAccessTest(AuthorizationTest):
    def setUp(self):
        super(HasCommandAccessTest, self).setUp()
        op_name = 'Commands.get_account_by_name'
        self.db._add_opset('public', [op_name])
        self.op = self.db._get_op(op_name)

    def testPublicCommand(self):
        self.assertTrue(self.auth_obj.has_access_to_command(self.op))

    def testUserAccessCommand(self):
        self.db._add_opset('public', []) # overwrites existing opset
        self.db._add_op_role(self.userid, 'orakel', self.userid)
        self.db._add_opset('orakel', [self.op])
        self.assertTrue(self.auth_obj.has_access_to_command(self.op))

if __name__ == '__main__':
    main()
