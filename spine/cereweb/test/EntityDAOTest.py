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

import time
import unittest
from lib.data.EntityDAO import EntityDAO
from lib.data.GroupDAO import GroupDAO
from lib.data.AccountDAO import AccountDAO
from lib.data.PersonDAO import PersonDAO
from lib.data.EntityFactory import EntityFactory
from CerebrumTestCase import CerebrumTestCase

import TestData

class EntityFactoryTest(CerebrumTestCase):
    def setUp(self):
        super(EntityFactoryTest, self).setUp()
        self.factory = EntityFactory(self.db)

    def test_get_group(self):
        entity = self.factory.get_entity(TestData.posix_group_id)

        self.assertEquals(TestData.posix_group_id, entity.id)
        self.assertEquals(TestData.posix_group_name, entity.name)
        self.assertEquals("group", entity.type_name)

    def test_group_speed(self):
        t = time.time()
        entity = self.factory.get_entity(TestData.large_group_id)
        d = time.time() - t
        self.assert_(d < 0.1, "this test should completet in under 100ms")

    def test_that_exists_returns_true_for_existing_id(self):
        dao = EntityDAO()
        result = dao.exists(TestData.bootstrap_account_id)
        self.assertTrue(result)

    def test_that_exists_returns_false_for_nonexisting_id(self):
        dao = EntityDAO()
        result = dao.exists(-2)
        self.assertFalse(result)

    def test_that_we_can_get_an_account_dao_given_an_accounts_entity_id(self):
        factory = EntityFactory()
        dao = factory.get_dao_by_entity_id(TestData.bootstrap_account_id)
        self.assertEqual(AccountDAO, dao.__class__)

    def test_that_we_can_get_a_person_dao_given_a_persons_entity_id(self):
        factory = EntityFactory()
        dao = factory.get_dao_by_entity_id(TestData.test_testesen_id)
        self.assertEqual(PersonDAO, dao.__class__)

    def test_that_we_can_get_a_group_dao_given_a_groups_entity_id(self):
        factory = EntityFactory()
        dao = factory.get_dao_by_entity_id(TestData.large_group_id)
        self.assertEqual(GroupDAO, dao.__class__)

    def test_that_we_can_get_an_entity_by_name(self):
        factory = EntityFactory()
        entity = factory.get_entity_by_name('group', TestData.posix_group_name)
        self.assertEqual('group', entity.type_name)
        self.assertEqual(TestData.posix_group_name, entity.name)
        self.assertEqual(TestData.posix_group_id, entity.id)
if __name__ == '__main__':
    unittest.main()
