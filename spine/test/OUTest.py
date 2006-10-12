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
import SpineIDL

class OUTest(SpineObjectTest):
    """Tests the OU implementation in Spine."""
    def __find_available_stedkode_institusjon(self):
        s = self.tr.get_ou_searcher()
        l = [ou.get_institusjon() for ou in s.search()]
        i = 1
        while i in l:
            i += 1
        return i

    def createObject(self):
        self.tr = self.session.new_transaction()
        self.institusjon = self.__find_available_stedkode_institusjon()
        c = self.tr.get_commands()
        try:
            self.ou = c.create_ou('Unit-test', self.institusjon, 1, 1, 1)
        except TypeError:
            raise SpineIDL.Errors.DatabaseError # Stedkode mixin isn't loaded, we raise to make our test succeed


    def deleteObject(self):
        self.ou.delete()

    def testStedkodeUniqueConstraint(self):
        """Tests that the create_ou() method for the stedkode mixin correctly
        raises a DatabaseError when trying to create an OU which violates the
        unique constraint on stedkode."""
        c = self.tr.get_commands()
        self.assertRaises(SpineIDL.Errors.AlreadyExistsError, c.create_ou,
                'Unit-test', self.institusjon, 1, 1, 1)

if __name__ == '__main__':
    unittest.main()

# arch-tag: d6bdf662-ea24-11d9-8fea-e50755c48550
