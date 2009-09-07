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
from lib.data.HistoryDAO import HistoryDAO
from CerebrumTestCase import CerebrumTestCase

group_id = 149
class HistoryDAOTest(CerebrumTestCase):
    def setUp(self):
        super(HistoryDAOTest, self).setUp()
        self.dao = HistoryDAO(self.db)

    def test_get_entity_history(self):
        events = self.dao.get_entity_history(group_id)

        count = 0
        for event in events:
            count += 1
            self.assert_(event.type in (
                "add",
                "del",
                "delete",
                "rem",
                "mod",
                "create",
                "group-promote"), event.type)
            self.assert_(event.creator != 'unknown')
            self.assert_(event.message)
            self.assert_(event.category)
            self.assert_(event.timestamp)
        self.assert_(count > 0)

if __name__ == '__main__':
    unittest.main()
