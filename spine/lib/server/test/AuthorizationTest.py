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
from pmock import *

import TestData
from MockDB import *

import sys
sys.path.append("..")
from Authorization import Authorization

class AuthorizationTestCase(TestCase):
    def setUp(self):
        self.db = MockDB(TestData.operation_sets)
        super(AuthorizationTestCase, self).setUp()

        if not hasattr(self, 'ac_dict'):
            self.ac_dict = TestData.accounts['user']
        self.op_public = self.db._get_op(TestData.operation_sets['public']['codestrs'][0])
        self.op_own_account = self.db._get_op(TestData.operation_sets['own_account']['codestrs'][0])
        self.op_orakel = self.db._get_op(TestData.operation_sets['orakel']['codestrs'][0])

        self.account = self.db._add_account(self.ac_dict)
        if self.ac_dict['superuser']:
            self.db._superuser(self.ac_dict['id'])
        else:
            self.db._no_superuser()
        self.userid = self.ac_dict['id']
        self.auth_obj = Authorization(self.account, database=self.db)

class PublicTest(AuthorizationTestCase):
    """Tests that do not depend on the contents of the database, or what rights a user is granted."""
    def setUp(self):
        super(PublicTest, self).setUp()
        self.obj = Mock()
        self.obj.pm = lambda x: x

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
        from Cerebrum.spine.Types import CodeType
        self.obj.__class__ = CodeType

        self.assertTrue(self.auth_obj.is_public(self.obj.__class__,
                                                self.obj, self.obj.pm))

    def testPublicCommand_has_permission(self):
        from Cerebrum.spine.Commands import Commands
        op = str(self.op_public).split('.')[1]
        self.obj.__class__ = Commands

        self.assertTrue(self.auth_obj.has_permission(self.obj, op))

    def testPublicCommand_has_access_to_command(self):
        self.assertTrue(self.auth_obj.has_access_to_command(self.op_public))

class SuperUserTest(AuthorizationTestCase):
    def setUp(self):
        self.ac_dict = TestData.accounts['bootstrap']
        super(SuperUserTest, self).setUp()

    def test_superuser(self):
        self.assertTrue(self.auth_obj.is_superuser())

    def test_has_permission(self):
        """Should always return true, no matter what arguments."""
        self.assertTrue(self.auth_obj.has_permission(None, None))

class UserTest(AuthorizationTestCase):
    def test_not_superuser(self):
        self.assertFalse(self.auth_obj.is_superuser())

    def testChangeOwnAccount(self):
        self.assertTrue(self.auth_obj.has_user_access(self.op_own_account, self.account))

    def testChangeOtherAccount(self):
        target = self.db._add_account(TestData.accounts['target'])
        self.assertFalse(self.auth_obj.has_user_access(self.op_own_account, target))

class OrakelTest(AuthorizationTestCase):
    def setUp(self):
        self.ac_dict = TestData.accounts['orakel']
        super(OrakelTest, self).setUp()

    def test_perm_granted_on_user(self):
        target = TestData.accounts['target']
        self.db._add_op_role(self.userid, 'orakel', target['id'])
        self.db._add_group_member(self.userid) # Stubs out group stuff.
        self.db._grant_access_to_entity_via_ou((self.userid,),hash(str(self.op_orakel)), target['id'])
        target = self.db._add_account(target)

        self.assertTrue(self.auth_obj.has_access(self.op_orakel, target))

    def test_perm_granted_on_group(self):
        group_id = self.userid + 5
        target = self.db._add_account(TestData.accounts['target'])
        target_id = TestData.accounts['target']['id']
        op_name = str(self.op_orakel)
        self.op = self.op_orakel
        self.db._add_group_member(group_id, self.userid)
        self.db._add_op_role(group_id, 'orakel', target_id)
        self.db._grant_access_to_entity_via_ou((self.userid, group_id), hash(op_name), target_id)
        self.assertTrue(self.auth_obj.has_access(self.op, target))

    def test_perm_granted_on_ou(self):
        ou = self.db._add_ou(TestData.ous['testou'])
        target = self.db._add_account(TestData.accounts['target'])

if __name__ == '__main__':
    main()
