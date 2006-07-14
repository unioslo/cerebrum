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
from TestBase import *

class TransactionTest(unittest.TestCase):
    def testMultiple(self):
        session1 = spine.login(username, password)
        session2 = spine.login(username, password)

        tr1 = session1.new_transaction()
        tr2 = session2.new_transaction()

        group = tr2.get_group_searcher().search()[0]

        assert group.get_name() == tr1.get_group(group.get_id()).get_name()

if __name__ == '__main__':
    unittest.main()
