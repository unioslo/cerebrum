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
import random
import string

from mx.DateTime import DateTime
import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError
from lib.data.AccountDAO import AccountDAO
from lib.data.AccountDTO import AccountDTO
from lib.data.ConstantsDAO import ConstantsDAO
from lib.data.DTO import DTO
from lib.data.EntityDAO import EntityDAO

from lib.templates.NewAccountViewTemplate import NewAccountViewTemplate

import TestData
from WriteTestCase import WriteTestCase

class AccountDAOTest(unittest.TestCase):
    """We test against the test-database and we use account 173870 as our testaccount.
    This is the ad-account in the NTNU test database."""

    def setUp(self):
        self.dao = AccountDAO()

    def test_noposix_account_has_correct_data(self):
        entity = self.dao.get(TestData.nonposix_account_id, include_extra=False)
        entity.groups = []
        expected = TestData.get_nonposix_account_dto()

        self.assertEqual(expected, entity)

    def test_posix_account_has_correct_data(self):
        entity = self.dao.get(TestData.posix_account_id, include_extra=False)
        entity.groups = []
        expected = TestData.get_posix_account_dto()

        self.assertEqual(expected, entity)

    def test_posix_account_has_primary_group(self):
        entity = self.dao.get(TestData.posix_account_id)
        expected = TestData.get_posix_account_primary_group_dto()
        primary_group = entity.primary_group

        self.assertEqual(expected, primary_group)

    def test_account_has_groups(self):
        entity = self.dao.get(TestData.posix_account_id)

        expected = DTO()
        expected.direct = True
        expected.description ='Group used in cereweb-tests'
        expected.type_name = 'group'
        expected.type_id = 18
        expected.id = TestData.posix_account_primary_group_id
        expected.name = 'test_posix'
        expected.is_posix = True

        actual = [g for g in entity.groups if g.id == expected.id][0]
        
        self.assertEqual(expected, actual)

    def test_that_groups_contains_primary_group(self):
        entity = self.dao.get(TestData.posix_account_id)

        group = [g for g in entity.groups if g.id == TestData.posix_account_primary_group_id][0]

        self.assertEqual(entity.primary_group.id, group.id)
        
    def test_account_has_creator(self):
        entity = self.dao.get(TestData.nonposix_account_id)
        expected = TestData.get_nonposix_account_creator_dto()
        creator = entity.creator
        
        self.assertEquals(expected, creator)

    def test_account_has_owner(self):
        entity = self.dao.get(TestData.nonposix_account_id)
        expected = TestData.get_nonposix_account_owner_dto()
        owner = entity.owner
        
        self.assertEquals(expected, owner)

    def test_account_affiliations(self):
        entity = self.dao.get(TestData.affiliated_account_id, include_extra=True)
        expected = TestData.get_affiliation_account_dto()

        found = False
        for affil in entity.affiliations:
            found |= affil == expected
        self.assert_(found)

    def test_account_passwords(self):
        entity = self.dao.get(TestData.posix_account_id, include_extra=True)
        expected = [
            "LANMAN-DES",
            "MD5-crypt",
            "SSHA",
            "PGP-offline",
            "PGP-kerberos",
            "crypt3-DES",
            "MD4-NT",
            "PGP-win_ntnu_no"]
        
        names = [a.methodname for a in entity.authentications]
        self.assertEqual(expected, names)

    def test_account_homes(self):
        entity = self.dao.get(TestData.affiliated_account_id, include_extra=True)
        homes = entity.homes
        home = filter(lambda x: x.spread.name == "user@stud", homes)
        self.assert_(len(home) == 1, "Forventet ett treff")
        home = home[0]

        expected = DTO()
        expected.spread = DTO()
        expected.spread.name = "user@stud"
        expected.path = "/home/homeq/be/bertil"
        expected.disk = None
        expected.status = DTO()
        expected.status.description = "Not created"

        self.assertEqual(expected, home)

    def test_account_spreads(self):
        entity = self.dao.get(TestData.affiliated_account_id, include_extra=True)
        spreads = [s.name for s in entity.spreads]

        expected = [
            'user@stud',
            'user@kerberos',
            'user@ntnu_ad',
            'user@cyrus_imap',
            'user@oppringt',
            'user@ldap',
        ]


        self.assertEqual(expected, spreads)

    def test_that_account_has_notes(self):
        entity = self.dao.get(TestData.noted_account_id, include_extra=True)
        self.assert_(len(entity.notes) == 1)

    def test_that_account_has_quarantines(self):
        entity = self.dao.get(TestData.quarantined_account_id, include_extra=True)
        self.assert_(len(entity.quarantines) == 1)
        
    def test_that_we_can_get_posix_groups_from_account_with_posix_groups(self):
        groups = self.dao.get_posix_groups(TestData.posix_account_id)
        
        self.assert_(len(groups) == 1)

    def test_that_account_without_posix_groups_gives_empty_list(self):
        groups = self.dao.get_posix_groups(TestData.account_without_posix_groups)

        self.assert_(len(groups) == 0)

    def test_that_we_can_get_available_uid(self):
        uid = self.dao.get_free_uid()
        
        self.assertRaises(NotFoundError, EntityDAO().get, uid)

    def test_that_we_can_get_default_shell(self):
        shell = self.dao.get_default_shell()

        self.assertEqual("bash", shell.name)
        self.assert_(shell.id is not None)

    def test_that_username_suggestions_works_for_one_word_name(self):
        group = DTO()
        group.name = "test"
        names = self.dao.suggest_usernames(group)
        self.assert_(group.name in names)
        self.assert_(len(names) >= 15)

    def test_that_username_suggestions_works_for_two_word_name(self):
        group = DTO()
        group.name = "test testesen"
        names = self.dao.suggest_usernames(group)
        self.assert_(len(names) >= 15)

class AccountDAOWriteTest(WriteTestCase):
    def setUp(self):
        super(AccountDAOWriteTest, self).setUp()
        self.dao = AccountDAO(self.db)

    def test_that_we_can_set_password_for_account(self):
        new_password = self._create_password()
        current_hash = self._get_current_hash(TestData.posix_account_id)
        
        self.dao.set_password(TestData.posix_account_id, new_password)

        changed_hash = self._get_current_hash(TestData.posix_account_id)

        self.assertNotEqual(changed_hash, current_hash, "Password should have changed.")

    def test_that_we_can_promote_account_to_posix(self):
        account_before = self.dao.get(TestData.nonposix_account_id)
        self.assertFalse(account_before.is_posix)

        posix_group = self.dao.get_posix_groups(TestData.nonposix_account_id)[0]
        
        self.dao.promote_posix(
            TestData.nonposix_account_id,
            posix_group.id)
        account_after = self.dao.get(TestData.nonposix_account_id)
        self.assertTrue(account_after.is_posix)

    def test_that_we_can_demote_account_from_posix(self):
        account_before = self.dao.get(TestData.posix_account_id)
        self.assertTrue(account_before.is_posix)
        
        self.dao.demote_posix(TestData.posix_account_id)

        account_after = self.dao.get(TestData.posix_account_id)
        self.assertFalse(account_after.is_posix)

    def test_that_we_can_delete_a_posix_account(self):
        account_before = self.dao.get(TestData.posix_account_id)
        
        self.dao.get(TestData.posix_account_id)
        self.dao.delete(TestData.posix_account_id)
        self.assertRaises(NotFoundError, self.dao.get, TestData.posix_account_id)
        
    def test_that_we_can_delete_a_non_posix_account(self):
        account_before = self.dao.get(TestData.nonposix_account_id)
        
        self.dao.get(TestData.nonposix_account_id)
        self.dao.delete(TestData.nonposix_account_id)
        self.assertRaises(NotFoundError, self.dao.get, TestData.nonposix_account_id)

    def test_that_we_can_create_an_account(self):
        dto = DTO()
        dto.name = 'xqxpqzaq'
        dto.owner = DTO()
        dto.owner = TestData.get_test_testesen()
        dto.expire_date = None
        dto.np_type = None

        self.assertRaises(NotFoundError, self.dao.get_by_name, dto.name)
        self.dao.create(dto)
        
        account = self.dao.get_by_name(dto.name)
        self.assert_(account.id >= 0)
        
    def _get_current_hash(self, account_id):
        return self.dao.get_md5_password_hash(account_id)

    def _create_password(self):
        new_password = [random.choice(string.ascii_lowercase) for x in xrange(3)]
        new_password += [random.choice(string.ascii_uppercase) for x in xrange(3)]
        new_password += [str(random.randint(10,99))]
        return "".join(new_password)

if __name__ == '__main__':
    unittest.main()
