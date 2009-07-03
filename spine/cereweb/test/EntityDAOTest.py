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

import TestData

class EntityDAOTest(unittest.TestCase):
    def test_get_group(self):
        entity = EntityDAO().get(TestData.posix_group_id)

        self.assertEquals(TestData.posix_group_id, entity.id)
        self.assertEquals(TestData.posix_group_name, entity.name)
        self.assertEquals("group", entity.type_name)

    def test_group_speed(self):
        t = time.time()
        entity = EntityDAO().get(TestData.large_group_id)
        d = time.time() - t
        self.assert_(d < 0.1, "this test should completet in under 100ms")

    def test_that_exists_returns_true_for_existing_id(self):
        result = EntityDAO().exists(TestData.bootstrap_account_id)
        self.assertTrue(result)

    def test_that_exists_returns_false_for_nonexisting_id(self):
        result = EntityDAO().exists(-2)
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()
