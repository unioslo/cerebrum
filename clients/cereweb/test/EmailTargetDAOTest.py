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
from CerebrumTestCase import CerebrumTestCase
from lib.data.DTO import DTO
from lib.data.EmailTargetDAO import EmailTargetDAO

class EmailTargetDAOTest(CerebrumTestCase):
    def setUp(self):
        super(EmailTargetDAOTest, self).setUp()
        self.dao = EmailTargetDAO(self.db)

   def test_that_get_from_entity_returns_correct_data(self):
        entity_id = 173691
        target = self.dao.get_from_entity(entity_id)
        self.assertEqual(None, target.alias)
        self.assertEqual('leiv.andenes@ntnu.no', target.primary.address)
        self.assertEqual(True, target.primary.is_primary)
        self.assertEqual(217124, target.id)
        self.assertEqual(173691, target.owner.id)
        self.assertEqual(306708, target.server.id)
        self.assertEqual(21, target.type_id)
        self.assertEqual(13, len(target.addresses))
        self.assertEqual('account', target.target_type)
        self.assertEqual('account@emanuel.itea.ntnu.no', target.name)

    def test_that_nonexisting_entity_gives_none(self):
        entity_id = -1
        target = self.dao.get_from_entity(entity_id)
        self.assertEqual(None, target)

if __name__ == '__main__':
    unittest.main()
