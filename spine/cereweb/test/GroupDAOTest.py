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

from mx.DateTime import DateTimeType
from lib.data.GroupDAO import GroupDAO
from lib.data.GroupDTO import GroupDTO

import cerebrum_path
from Cerebrum.Errors import NotFoundError

import TestData
from WriteTestCase import WriteTestCase

class GroupDAOTest(unittest.TestCase):
    """We test against the test-database and we use 4 fabricated groups with 4 fabricated members that have 1 fabricated owners."""
    def setUp(self):
        self.dao = GroupDAO()

    def test_get_entity(self):
        group = self.dao.get_entity(TestData.large_group_id)
        self.assert_(group.id == TestData.large_group_id)

    def test_get_group_by_name(self):
        group = self.dao.get_by_name(TestData.posix_group_name)
        self.assert_(group.id == TestData.posix_group_id)

    def test_posix_group_has_correct_data(self):
        expected = TestData.get_fake_posix_group()

        group = self.dao.get(TestData.posix_group_id, include_extra=True)
        group.members = []

        self.assertEqual(expected, group)

    def test_that_posix_group_has_cetest1_as_member(self):
        expected = TestData.get_cetest1()
        
        group = self.dao.get(TestData.posix_group_id, include_extra=True)

        found = False
        for member in group.members:
            found |= member == expected
        
        self.assert_(found)
        

    def test_expired_posix_group_is_expired(self):
        group = self.dao.get(TestData.expired_group_id)

        self.assert_(group.is_expired)

    def test_non_posix_group_has_gid_neg1(self):
        group = self.dao.get(TestData.nonposix_group_id)

        self.assertEqual(-1, group.posix_gid)
        self.assertFalse(group.is_posix)

    def test_quarantines(self):
        group = self.dao.get(TestData.quarantined_group_id)

        for q in group.quarantines:
            self.assert_(q.type_name in ("sperret", "remote", "slutta", "svakt_passord"))
            self.assert_(q.type_description)
            self.assert_(q.description)
            self.assert_(q.creator.id >= 0)
            self.assert_(q.creator.name == "bootstrap_account")
            self.assert_(q.creator.type_name == "account")
            for date in (q.create_date, q.start_date, q.end_date, q.disable_until):
                self.assertValidDate(date)

    def test_notes(self):
        group = self.dao.get(TestData.notes_group_id)
        
        for note in group.notes:
            self.assert_(note.id >= 0)
            self.assert_(note.subject)
            self.assert_(note.creator.id >= 0)
            self.assert_(note.creator.name == "bootstrap_account")
            self.assert_(note.creator.type_name == "account")
            self.assertValidDate(note.create_date)
            self.assert_(note.description)

    def test_spreads(self):
        group = self.dao.get(TestData.spread_group_id, include_extra=True)

        self.assert_(len(group.spreads) == 1)
        for spread in group.spreads:
            self.assert_(spread.name)
            self.assert_(spread.description)

    def test_get_nonexisting_throws_NotFoundException(self):
        self.assertRaises(NotFoundError, self.dao.get, -1)

    def test_get_entities_for_account(self):
        expected = TestData.get_posix_account_primary_group_dto()
        expected.is_posix = True
        expected.description = 'Group used in cereweb-tests'
        groups = self.dao.get_entities_for_account(TestData.posix_account_id)

        found = False
        for group in groups:
            found |= group == expected
        
        self.assert_(found)
        
    def test_that_get_groups_on_groupless_account_returns_empty_list(self):
        groups = self.dao.get_groups_for(TestData.groupless_account_id)
        
        self.assert_(len(groups) == 0)
        self.assert_(type(groups) == list)

    def assertValidDate(self, date):
        self.assert_(date is None or isinstance(date, DateTimeType))

class GroupDaoWriteTest(WriteTestCase):
    def setUp(self):
        super(GroupDaoWriteTest, self).setUp()
        self.dao = GroupDAO(self.db)

    def test_add_member(self):
        group_id = TestData.quarantined_group_id
        found = self._group_has_member(group_id, TestData.account_cetest1)        
        self.assert_(not found, "should not be member before test is run")

        self.dao.add_member(TestData.account_cetest1, group_id)

        found = self._group_has_member(group_id, TestData.account_cetest1, db=self.db)        
        self.assert_(found, "should be member")

    def test_create(self):
        data = self._create_group("gtest_create_tmp")

        group = self._add(data)
        
        self.assert_(group.name == data.name)

    def test_delete(self):
        data = self._create_group("gtest_del_tmp")
        group = self._add(data)

        self.dao.get(group.id)

        self.dao.delete(group.id)

        self.assertRaises(NotFoundError, self.dao.get, group.id)

    def test_that_we_can_delete_a_posix_group(self):
        data = self._create_group("gtest_del_tmp")
        group = self._add(data)

        self.dao.promote_posix(group.id)

        self.dao.delete(group.id)

        self.assertRaises(NotFoundError, self.dao.get, group.id)

    def test_promote_posix(self):
        data = self._create_group("gtest_pro_tmp")
        group = self._add(data)
        self.assert_(not group.is_posix)

        self.dao.promote_posix(group.id)

        group = self.dao.get_by_name(data.name)
        self.assert_(group.is_posix)
        
    def test_demote_posix(self):
        data = self._create_group("gtest_pro_tmp")
        group = self._add(data)
        self.dao.promote_posix(group.id)
        group = self.dao.get_by_name(data.name)
        self.assert_(group.is_posix)

        self.dao.demote_posix(group.id)
        group = self.dao.get_by_name(data.name)

        self.assert_(not group.is_posix)

    def test_edit(self):
        data = self._create_group("gtest_pro_tmp")
        group = self._add(data)

        group.description = "I got changed."
        self.dao.save(group)

        result = self.dao.get(group.id)
        self.assert_(group.description == result.description)

    def _add(self, data):
        self.dao.add(data)
        return self.dao.get_by_name(data.name)

    def _group_has_member(self, group_id, account_id, db=None):
        if db is None:
            group = GroupDAO().get(group_id, include_extra=True)
        else:
            group = GroupDAO(db).get(group_id, include_extra=True)

        for member in group.members:
            if member.id == account_id:
                return True
        return False

    def _create_group(self, name):
        group = GroupDTO()
        group.name = name
        group.description = "please delete me, I'm not meant to exist"
        return group


if __name__ == '__main__':
    unittest.main()
