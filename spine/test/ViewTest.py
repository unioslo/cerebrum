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
        spread = tr.get_spread_searcher().search()[0]
        view = tr.get_view()
        view.set_spread(spread)
        print view.account()
        print view.account_quarantine()
        print view.group()
        print view.person()
        print view.primary_user()
        print view.ou()

        for row in view.test():
            for i in row:
                print [i.key, i.value, i.int_value, i.is_none]


if __name__ == '__main__':
    unittest.main()
