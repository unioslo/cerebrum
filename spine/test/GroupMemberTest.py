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
import time
from TestBase import *

class GroupMemberTest(unittest.TestCase):
    def testGroupMember(self):
        session = spine.login(username, password)
        try:
            tr = session.new_transaction()

            groupmembers = tr.get_group_member_searcher()
            groups = tr.get_group_searcher()

            groupmembers.add_join('group', groups, 'id')

            groupmembers.set_search_limit(100, 0)
            
#            print j.search_sql()
            for i in groupmembers.dump_rows():
                print ' '.join([i for i in i])
            a, b = groupmembers.get_dumpers()
            a, b = groupmembers.get_search_objects()
            print a._is_equivalent(groups), b._is_equivalent(groups)
            print a, b, groups, groupmembers, 
        finally:
            session.logout()

if __name__ == '__main__':
    unittest.main()

# arch-tag: d6a10e36-31c2-11da-8244-9d48f41c04b3
