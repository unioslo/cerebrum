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
from lib.data.OuDAO import OuDAO
from CerebrumTestCase import CerebrumTestCase

class OuDAOTest(CerebrumTestCase):
    def setUp(self):
        super(OuDAOTest, self).setUp()
        self.dao = OuDAO(self.db)
    
    def test_that_get_tree_in_kjernen_gives_8_roots(self):
        roots = self.dao.get_tree("Kjernen")
        self.assertEqual(8, len(roots))
        self.assertEqual(3, roots[0].id)

    def test_that_get_entities_returns_x_ous(self):
        entities = self.dao.get_entities()
        self.assertEqual(138, len(entities))

    def test_that_the_ou_contains_enough_information(self):
        ou = self.dao.get(55)
        self.assertEqual(55, ou.id)
        self.assertEqual("NT Fakultetsadministrasjon", ou.name)
        self.assertEqual("NT-ADM", ou.acronym)
        self.assertEqual("NT-ADM", ou.short_name)
        self.assertEqual("NT Fakultetsadministrasjon", ou.display_name)
        self.assertEqual("NT Fakultetsadministrasjon", ou.sort_name)
        self.assertEqual(0, ou.landkode)
        self.assertEqual("00000194660100", ou.stedkode)
        self.assertEqual(194, ou.institusjon)
        self.assertEqual(66, ou.fakultet)
        self.assertEqual(1, ou.institutt)
        self.assertEqual(0, ou.avdeling)

    def test_that_we_can_create_an_ou(self):
        name = "test"
        institution, faculty, institute, department = 1, 2, 3, 4
        acronym, short_name, display_name, sort_name = "A", "B", "C", "D"
        ou_id = self.dao.create(name, institution, faculty, institute, department, acronym, short_name, display_name, sort_name)

        ou = self.dao.get(ou_id)
        self.assertEqual(institution, ou.institusjon)
        self.assertEqual(faculty, ou.fakultet)
        self.assertEqual(institute, ou.institutt)
        self.assertEqual(department, ou.avdeling)
        self.assertEqual(acronym, ou.acronym)
        self.assertEqual(short_name, ou.short_name)
        self.assertEqual(display_name, ou.display_name)
        self.assertEqual(sort_name, ou.sort_name)

if __name__ == '__main__':
    unittest.main()

# arch-tag: c9944718-f3a0-11d9-8f80-6ca94c3e384f
