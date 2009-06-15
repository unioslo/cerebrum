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
from mx.DateTime import DateTime
import cerebrum_path
from Cerebrum import Utils
from lib.data import PersonDAO

import TestData

class PersonDAOTest(unittest.TestCase):
    """We test against the test-database and we use the fabricated person Test Testesen to verify that we get the expected data."""

    def test_person_has_correct_data(self):
        group = PersonDAO.get(354985)
        expected = TestData.get_test_testesen()

        self.assertEqual(expected, group)

if __name__ == '__main__':
    unittest.main()

# arch-tag: c9944718-f3a0-11d9-8f80-6ca94c3e384f
