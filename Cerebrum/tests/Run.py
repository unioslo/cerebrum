#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# Copyright 2002, 2003 University of Oslo, Norway
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

import unittest

import cerebrum_path
from Cerebrum.tests import EntityTestCase
from Cerebrum.tests.OUTestCase import OUTestCase
from Cerebrum.tests.PersonTestCase import PersonTestCase
from Cerebrum.tests.AccountTestCase import AccountTestCase
from Cerebrum.tests import GroupTestCase
from Cerebrum.tests.SQLDriverTestCase import SQLDriverTestCase

def suite():
    """Returns a suite containing all the test cases in this module.
       It can be a good idea to put an identically named factory function
       like this in every test module. Such a naming convention allows
       automation of test discovery.
    """

    #suite1 = SQLDriverTestCase.suite()
    suite2 = OUTestCase.suite()
    suite3 = PersonTestCase.suite()
    suite4 = AccountTestCase.suite()
    suite5 = GroupTestCase.suite()
    suite6 = EntityTestCase.suite()
    return unittest.TestSuite((suite6, suite2, suite3, suite4, suite5))

if __name__ == '__main__':
    # When this module is executed from the command-line, run all its tests
    unittest.main(defaultTest='suite')

# arch-tag: 0a2c5fe2-c56e-43a0-b072-90e6d3fbe5b6
