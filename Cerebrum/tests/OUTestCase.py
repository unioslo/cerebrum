#!/usr/bin/env python2.2
#
# $Id$

import unittest
from Cerebrum import Database
from Cerebrum import OU
from Cerebrum import Person
from Cerebrum import Account
from Cerebrum import Constants

class OU_createTestCase(unittest.TestCase, object): # 'object' because
    # unittest isn't an object, and we want to be allowed to call super

    Cerebrum = Database.connect()
    co = Constants.Constants(Cerebrum)

    ou_dta = {'stednavn': "Stednavn", 'acronym': 'Acronym',
         'short_name': 'short_name', 'display_name': 'display_name',
         'sort_name': 'sort_name',
         'addr': 'addr', 'zip':'zip', 'city': 'city'
         }

    def _myPopulateOU(self, ou):
        ou.populate(self.ou_dta['stednavn'], acronym=self.ou_dta['acronym'],
                    short_name=self.ou_dta['short_name'],
                    display_name=self.ou_dta['display_name'],
                    sort_name=self.ou_dta['sort_name'])
        ou.affect_addresses(self.co.system_lt, self.co.address_street)
        ou.populate_address(self.co.address_street, addr=self.ou_dta['addr'],
                            zip=self.ou_dta['zip'],
                            city=self.ou_dta['city'])
        
    def setUp(self):
        print "OU_createTestCase.setUp()"
        new_ou = OU.OU(self.Cerebrum)
        new_ou.clear()
        self._myPopulateOU(new_ou)
        new_ou.write_db()
        self.ou_id = new_ou.ou_id

    def tearDown(self):
        print "OU_createTestCase.tearDown()"

class OUTestCase(OU_createTestCase):
    def testCompareOU(self):
        ou = OU.OU(self.Cerebrum)
        ou.find(self.ou_id)
        new_ou = OU.OU(self.Cerebrum)
        new_ou.clear()
        self._myPopulateOU(new_ou)
        self.failIf(new_ou <> ou, "Error: should be equal")
        ou.populate('test')
        self.failIf(new_ou == ou, "Error: should be different")

    def suite():
        suite = unittest.TestSuite()
        suite.addTest(OUTestCase("testCompareOU"))
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
    # When this module is executed from the command-line, run all its tests
    unittest.main(defaultTest='suite')
