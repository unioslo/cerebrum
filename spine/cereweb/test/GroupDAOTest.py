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
from lib.data import GroupDAO
from lib.data.GroupDTO import GroupDTO
import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError
Database = Utils.Factory.get("Database")
import TestData

class GroupDAOTest(unittest.TestCase):
    """We test against the test-database and we use 4 fabricated groups with 4 fabricated members that have 1 fabricated owners."""

    def test_get_large_group_by_id(self):
        """This was a bootstrap test, but is now used to get a feel for
        the performance of the DAOs."""
        group = GroupDAO.get(TestData.large_group_id, include_members=True)
        self.assert_(group.id == TestData.large_group_id)

    def test_get_shallow_large_group(self):
        group = GroupDAO.GroupDAO().get_shallow(TestData.large_group_id)
        self.assert_(group.id == TestData.large_group_id)

    def test_get_group_by_name(self):
        group = GroupDAO.get_by_name(TestData.posix_group_name)
        self.assert_(group.id == TestData.posix_group_id)

    def test_posix_group_has_correct_data(self):
        expected = TestData.get_fake_posix_group()

        group = GroupDAO.get(TestData.posix_group_id, include_members=True)

        self.assertEqual(expected, group)

    def test_expired_posix_group_is_expired(self):
        group = GroupDAO.get(TestData.expired_group_id)

        self.assert_(group.is_expired)

    def test_non_posix_group_has_gid_neg1(self):
        group = GroupDAO.get(TestData.nonposix_group_id)

        self.assertEqual(-1, group.posix_gid)
        self.assertFalse(group.is_posix)

    def test_quarantines(self):
        group = GroupDAO.get(TestData.quarantined_group_id)

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
        group = GroupDAO.get(TestData.notes_group_id)
        
        for note in group.notes:
            self.assert_(note.id >= 0)
            self.assert_(note.subject)
            self.assert_(note.creator.id >= 0)
            self.assert_(note.creator.name == "bootstrap_account")
            self.assert_(note.creator.type_name == "account")
            self.assertValidDate(note.create_date)
            self.assert_(note.description)

    def test_spreads(self):
        group = GroupDAO.get(TestData.spread_group_id)

        self.assert_(len(group.spreads) == 1)
        for spread in group.spreads:
            self.assert_(spread.name)
            self.assert_(spread.description)

    def test_get_nonexisting_throws_NotFoundException(self):
        self.assertRaises(NotFoundError, GroupDAO.get, -1)

    def assertValidDate(self, date):
        self.assert_(date is None or isinstance(date, DateTimeType))

class GroupDaoWriteTest(unittest.TestCase):
    def setUp(self):
        self.db = Database()
        self.db.change_program = "unit test"
        self.db.change_by = 2
        self.dao = GroupDAO.GroupDAO(self.db)

    def tearDown(self):
        self.db.rollback()

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
            group = GroupDAO.get(group_id, include_members=True)
        else:
            group = GroupDAO.GroupDAO(db).get(group_id, include_members=True)

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
