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
import traceback
from Cerebrum import Errors
from Cerebrum import OU
from Cerebrum import Person
from Cerebrum import Account
from Cerebrum import Constants
from Cerebrum.Utils import Factory

# Explicitly inherit from `object` because unittest isn't a new-style
# class, and we want to be allowed to call super.
class OU_createTestCase(unittest.TestCase, object):

    Cerebrum = Factory.get('Database')()
    Cerebrum.cl_init(change_program="OUTestCase")
    co = Factory.get('Constants')(Cerebrum)

    ou_dta = {
        'stednavn': "Stednavn",
        'acronym': 'Acronym',
        'short_name': 'short_name',
        'display_name': 'display_name',
        'sort_name': 'sort_name',
        'addr': 'addr',
        'postal_number':'post_n',
        'city': 'city'
        }

    def _myPopulateOU(self, ou):
        ou.populate(self.ou_dta['stednavn'], acronym=self.ou_dta['acronym'],
                    short_name=self.ou_dta['short_name'],
                    display_name=self.ou_dta['display_name'],
                    sort_name=self.ou_dta['sort_name'])
        ou.populate_address(self.co.system_manual,
                            self.co.address_street,
                            address_text=self.ou_dta['addr'],
                            postal_number=self.ou_dta['postal_number'],
                            city=self.ou_dta['city'])

    def setUp(self):
        try:
            # print "OU_createTestCase.setUp()"
            new_ou = OU.OU(self.Cerebrum)
            self._myPopulateOU(new_ou)
            new_ou.write_db()
            self.ou_id = new_ou.entity_id
        except:
            print "error: unable to create OU."
            traceback.print_exc()

    def tearDown(self):
        # print "OU_createTestCase.tearDown()"
        self.Cerebrum.execute("""
        DELETE FROM [:table schema=cerebrum name=ou_info]
        WHERE ou_id=:id""", {'id': self.ou_id})
        self.Cerebrum.commit()


class OUTestCase(OU_createTestCase):

    def testCreateOU(self):
        "Test that one can create an OU"
        self.failIf(not hasattr(self, "ou_id"))

    def testCompareOU(self):
        "Compare created OU from database with set values"
        ou = OU.OU(self.Cerebrum)
        ou.find(self.ou_id)
        new_ou = OU.OU(self.Cerebrum)
        self._myPopulateOU(new_ou)
        self.failIf(new_ou <> ou, "Error: should be equal")
        ou.populate('test')
        self.failIf(new_ou == ou, "Error: should be different")

    def testDeleteOU(self):
        "Delete the OU"
        # This is actually a clean-up method, as we don't support
        # deletion of OUs
        self.tearDown()
        ou = OU.OU(self.Cerebrum)
        self.assertRaises(Errors.NotFoundError, ou.find, self.ou_id)

    def suite():
        suite = unittest.TestSuite()
        suite.addTest(OUTestCase("testCreateOU"))
        suite.addTest(OUTestCase("testCompareOU"))
        suite.addTest(OUTestCase("testDeleteOU"))
        return suite
    suite = staticmethod(suite)


def suite():
    """Returns a suite containing all the test cases in this module.

    It can be a good idea to put an identically named factory function
    like this in every test module. Such a naming convention allows
    automation of test discovery.

    """

    suite1 = OUTestCase.suite()
    return unittest.TestSuite((suite1,))


if __name__ == '__main__':
    # When executed as a script, perform all tests in suite().
    unittest.main(defaultTest='suite')

# arch-tag: f43b6ca0-3ee7-49e6-9603-e81d7ec48e65
