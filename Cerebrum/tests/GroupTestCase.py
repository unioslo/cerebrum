#! /usr/bin/env python2.2
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
import pprint

from Cerebrum import Constants
from Cerebrum import Database
from Cerebrum import Account
from Cerebrum import Group
from Cerebrum.tests.AccountTestCase import Account_createTestCase


class Group_createTestCase(Account_createTestCase):

    def setUp(self):
        super(Group_createTestCase, self).setUp()
        group = Group.Group(self.Cerebrum)
        self._populate_group(group)
        group.write_db()
        self.group_id = group.entity_id
        self.group = group
        self.members = ()

    def _populate_group(self, group, **group_args):
        if not group_args:
            group_args = {
                'creator_id': self.account.entity_id, # from AccountTestCase.py
                'visibility': Group_createTestCase.co.group_visibility_all,
                'name': 'test_group',
                'description': "Test suite's test group."
                }
        # group.clear()
        group.populate(group_args['creator_id'], group_args['visibility'],
                       group_args['name'], group_args['description'])

    def tearDown(self):
        group = Group.Group(self.Cerebrum)
        group.find(self.group_id)
        group.delete()
        for id in self.members:
            self.Cerebrum.execute("""
            DELETE FROM [:table schema=cerebrum name=entity_name]
            WHERE entity_id=:id""", {'id': id})
            self.Cerebrum.execute("""
            DELETE FROM [:table schema=cerebrum name=account_info]
            WHERE account_id=:id""", {'id': id})
        super(Group_createTestCase, self).tearDown()


class GroupTestCase(Group_createTestCase):

    def testCreateGroup(self):
        "Test group creation."
        self.failIf(not hasattr(self, 'group_id'),
                    "Error: Something went wrong in test group creation.")

    def testCompareGroup(self):
        "Test comparison operation on group object retrieved from database."
        g1 = Group.Group(self.Cerebrum)
        g1.find(self.group_id)
        self.failIf(not g1._Group__in_db, "Error: g1.__in_db is false.")
        self.failIf(g1._Group__updated, "Error: g1.__updated is true.")

        g2 = Group.Group(self.Cerebrum)
        self._populate_group(g2)
        self.failIf(g2._Group__in_db, "Error: g2.__in_db is true.")
        self.failIf(not g2._Group__updated, "Error: g2.__updated is false.")

        self.failIf(g1 <> g2, "Error: Groups should be equal.")
        g1.group_name = g2.group_name + 'x'
        self.failIf(not g1._Group__updated, "Error: g1.__updated still false.")
        self.failIf(g1 == g2, "Error: Groups should differ.")

    def testAddRemoveMember(self):
        "Test simple member add and remove on groups."
        u, i, d = self.group.list_members()
        self.failIf((self.co.entity_account, self.account_id) in u,
                    "About to add account member; already in group.")
        self.failIf(u or i or d, "Fresh group should have no members.")
        self.group.add_member(self.account.entity_id, self.account.entity_type,
                              self.co.group_memberop_union)
        u, i, d = self.group.list_members()
        self.failUnless((self.co.entity_account, self.account_id) in u,
                        "Added account member; not in group.")
        self.group.remove_member(self.account.entity_id,
                                 self.co.group_memberop_union)
        u, i, d = self.group.list_members()
        self.failIf((self.co.entity_account, self.account_id) in u,
                    "Removed account member; still in group.")

    def testListMembers(self):
        "Test (recursively) listing members of groups."
        account = Account.Account(self.Cerebrum)
        # TODO: Here we should add members in a complex way and read them back
        i = 0

        # This datastructure defines a set of groups/accounts to
        # create, and adds them to their corresponding group using the
        # indicated membership operation.  A group/account that
        # occours multiple times will only be created once.

        dta = (
            ('g', 'group_1',
             ('a', 'account_1', 'u'),
             ('a', 'account_2', 'u')),
            ('g', 'group_2',
             ('a', 'account_1', 'u')),
            ('g', 'group_3',
             ('a', 'account_3', 'u'),
             ('g', 'group_1', 'u'),
             ('g', 'group_2', 'i')),
            ('g', 'group_4',
             ('g', 'group_3', 'u'),
             ('g', 'group_2', 'd'))
            )
        i = 0
        while i < 5:
            i += 1
            account.clear()
            self._myPopulateAccount(account)
            account.account_name += "_%s" % i
            account.write_db()
            self.members += (account.entity_id, )
            self.group.add_member(account.entity_id, account.entity_type,
                                  Group_createTestCase.co.group_memberop_union)

        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(self.group.list_members())


def suite():
    #    return unittest.makeSuite(GroupTestCase, 'test')
    suite = unittest.TestSuite()
    suite.addTest(GroupTestCase("testCreateGroup"))
    suite.addTest(GroupTestCase("testCompareGroup"))
    suite.addTest(GroupTestCase("testAddRemoveMember"))
    suite.addTest(GroupTestCase("testListMembers"))
    return suite


if __name__ == '__main__':
    # When executed as a script, perform all tests in suite().
    unittest.main(defaultTest='suite')
