#! /usr/bin/env python2.2

import unittest

from Cerebrum import Constants
from Cerebrum import Database
from Cerebrum import Account
from Cerebrum import Group
from Cerebrum.tests.AccountTestCase import Account_createTestCase
import pprint

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
            account = Account.Account(self.Cerebrum)
            account.find(self.account_id)
            group_args = {
                'creator': account,
                'visibility': Group_createTestCase.co.group_visibility_all,
                'name': 'test_group',
                'description': "Test suite's test group."
                }
        # group.clear()
        group.populate(group_args['creator'], group_args['visibility'],
                       group_args['name'], group_args['description'])

    def tearDown(self):
        group = Group.Group(self.Cerebrum)
        group.find(self.group_id)
        group.delete()
        for id in self.members:
            self.Cerebrum.execute(
                """DELETE FROM [:table schema=cerebrum name=entity_name]
                WHERE entity_id=:id""", {'id': id})
            self.Cerebrum.execute(
                """DELETE FROM [:table schema=cerebrum name=account_info]
                WHERE account_id=:id""", {'id': id})
        super(Group_createTestCase, self).tearDown()
        self.Cerebrum.commit()

class GroupTestCase(Group_createTestCase):
    def testCreateGroup(self):
        "Test group creation."
        self.failIf(getattr(self, 'group_id', None) is None,
                    "Error: Something went wrong in test group creation.")

    def testCompareGroup(self):
        "Test comparison operation on group object retrieved from database."
        g1 = Group.Group(self.Cerebrum)
        g1.find(self.group_id)
        self.failIf(not g1._Group__in_db, "Error: g1.__in_db is false.")
        self.failIf(g1._Group__updated, "Error: g1.__updated is true.")

        g2 = Group.Group(self.Cerebrum)
        self._populate_group(g2)
        self.failIf(g2._Group__in_db, "Error: g2.__in_db should is true.")
        self.failIf(not g2._Group__updated, "Error: g2.__updated is false.")

        self.failIf(g1 <> g2, "Error: Groups should be equal.")
        g1.group_name = g2.group_name + 'x'
        self.failIf(not g1._Group__updated, "Error: g1.__updated not true.")
        self.failIf(g1 == g2, "Error: Groups should differ.")

    def testAddMember(self):
        "Test adding members to groups."
        account = Account.Account(self.Cerebrum)
        account.find(self.account_id)
        self.group.add_member(account, Group_createTestCase.co.group_memberop_union)
        # TODO: Assuming that it worked, should add test to verify this

    def testRemoveMember(self):
        "Test removing members from groups."
        account = Account.Account(self.Cerebrum)
        account.find(self.account_id)
        self.group.remove_member(account, Group_createTestCase.co.group_memberop_union)
        # TODO: Verify that it worked

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
            self.group.add_member(account,
                                  Group_createTestCase.co.group_memberop_union)

        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(self.group.list_members())

def suite():
    #    return unittest.makeSuite(GroupTestCase, 'test')
    suite = unittest.TestSuite()
    suite.addTest(GroupTestCase("testAddMember"))
    suite.addTest(GroupTestCase("testListMembers"))
    suite.addTest(GroupTestCase("testRemoveMember"))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
