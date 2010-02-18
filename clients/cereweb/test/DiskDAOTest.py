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
from lib.data.DTO import DTO
from lib.data.DiskDAO import DiskDAO
from CerebrumTestCase import CerebrumTestCase

import TestData

class DiskDAOTest(CerebrumTestCase):
    def setUp(self):
        super(DiskDAOTest, self).setUp()
        self.dao = DiskDAO(self.db)

    def test_search(self):
        disks = DiskDAO().search()
        self.assertEqual(13, len(disks))

    def test_get(self):
        expected = TestData.ahomea
        disk = self.dao.get(expected.id)
        self.assertEqual(expected, disk)

if __name__ == '__main__':
    unittest.main()
