#!/usr/bin/env python2.2
#
# $Id$

import unittest
import traceback
from Cerebrum import Database
from Cerebrum import Errors
from Cerebrum import OU
from Cerebrum import Person
from Cerebrum import Account
from Cerebrum import Constants


# Explicitly inherit from `object` because unittest isn't a new-style
# class, and we want to be allowed to call super.
class OU_createTestCase(unittest.TestCase, object):

    Cerebrum = Database.connect()
    co = Constants.Constants(Cerebrum)

    ou_dta = {
        'stednavn': "Stednavn",
        'acronym': 'Acronym',
        'short_name': 'short_name',
        'display_name': 'display_name',
        'sort_name': 'sort_name',
        'addr': 'addr',
        'zip':'zip',
        'city': 'city'
        }

    def _myPopulateOU(self, ou):
        ou.populate(self.ou_dta['stednavn'], acronym=self.ou_dta['acronym'],
                    short_name=self.ou_dta['short_name'],
                    display_name=self.ou_dta['display_name'],
                    sort_name=self.ou_dta['sort_name'])
        ou.affect_addresses(self.co.system_manual, self.co.address_street)
        ou.populate_address(self.co.address_street, addr=self.ou_dta['addr'],
                            zip=self.ou_dta['zip'],
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
