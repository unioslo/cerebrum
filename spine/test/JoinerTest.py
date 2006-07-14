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

class JoinerTest(unittest.TestCase):
    def testGroupMember(self):
        session = spine.login(username, password)
        try:
            tr = session.new_transaction()
            j = tr.get_group_member_searcher()
#            gm.set_posix_gid_more_than(1090)
#            j = tr.get_joiner(gm)

            n = tr.get_entity_name_searcher()
            n.set_value_domain(tr.get_value_domain('group_names'))
            j.add_join(n, 'entity', 'group')

#            j.order_by_desc(gm, 'id')
#            j.limit(5)
            
#            print j.search_sql()
            for i in j.dump_rows():
                print ' '.join([i for i in i])
        finally:
            session.logout()

    def testAccount(self):
        session = spine.login(username, password)
        try:
            tr = session.new_transaction()

            spread = tr.get_spread('user@stud')


            ac = tr.get_account_searcher()
            joiner = tr.get_joiner(ac)
            joiner = ac

            n = tr.get_entity_name_searcher()
            n.set_value_domain(tr.get_value_domain('account_names'))
            joiner.add_join(n, 'entity', 'id')

            s = tr.get_entity_spread_searcher()
            s.set_entity_type(tr.get_entity_type('account'))
            s.set_spread(spread)
            joiner.add_join(s, 'entity', 'id')

            h = tr.get_account_home_searcher()
            h.set_spread(spread)
            joiner.add_left_join(h, 'account', 'id')

            # FIXME: 
            #h = tr.get_home_directory_seacher()

            md5 = tr.get_account_authentication_searcher()
            md5.set_method(tr.get_authentication_type('MD5-crypt'))
            joiner.add_left_join(md5, 'account', 'id')

            des = tr.get_account_authentication_searcher()
            des.set_method(tr.get_authentication_type('crypt3-DES'))
            joiner.add_left_join(des, 'account', 'id')

            """
            person = tr.get_person_name_searcher()
            person.set_name_variant(tr.get_name_type('FULL'))
            person.set_source_system(tr.get_source_system('Cached'))
            joiner.add_left_join(person, 'owner', 'person')

            last = tr.get_person_name_searcher()
            last.set_name_variant(tr.get_name_type('LAST'))
            last.set_source_system(tr.get_source_system('Cached'))
            joiner.add_left_join(last, 'owner', 'person')

            person = tr.get_entity_searcher()
            joiner.add_join(person, 'owner', 'id')

            joiner.order_by(last, 'name')

            """
#            print joiner.search_sql()
            result = joiner.dump_rows()
            print result
#            for i in result:
#                print ' '.join([i for i in i])
#            print
            print 'hits:', len(result)
        finally:
            session.logout()

if __name__ == '__main__':
    unittest.main()

# arch-tag: d6a10e36-31c2-11da-8244-9d48f41c04b3
