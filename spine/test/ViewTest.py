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

class ViewTest(unittest.TestCase):
    def testAccountView(self):
        session = spine.login(username, password)
        tr = session.new_transaction()
        view = tr.get_view()
        view.set_spread(tr.get_spread('user@stud'))
        print view.account()
        print view.account_quarantine()
        print view.group()
        print view.person()
        print view.primary_user()
        print view.ou()

        for row in view.test():
            for i in row:
                print [i.key, i.value, i.int_value, i.is_none]

        tr.rollback()
        session.logout()

    def testMany(self):
        import time
        a = time.time()
        for i in range(100):
            session = spine.login(username, password)
            session.logout()
        print '\ntime used for spine.login:', time.time() - a
        a = time.time()
        session = spine.login(username, password)
        for i in range(100):
            tr = session.new_transaction()
            tr.get_group(89)
            tr.rollback()
        session.logout()
        print '\ntime used for spine.login:', time.time() - a

    def testGroupMember(self):
        session = spine.login(username, password)
        try:
            tr = session.new_transaction()
            view = tr.get_view()
            view.set_spread(tr.get_spread('user@stud'))

            groups = {}
            for i in view.group_members():
                try:
                    groups[i.key].append(i.value)
                except KeyError:
                    groups[i.key] = [i.value]
                    
            for key, value in groups.items():
                print key, value
        finally:
            session.logout()


if __name__ == '__main__':
    unittest.main()

# arch-tag: d6a10e36-31c2-11da-8244-9d48f41c04b3
