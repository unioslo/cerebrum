#!/usr/bin/env python2.2

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
from Cerebrum import Database
from Cerebrum import Errors
from Cerebrum import OU
from Cerebrum import Person
from Cerebrum import Account
from Cerebrum import Constants

from Cerebrum.tests.OUTestCase import OU_createTestCase


class Person_createTestCase(OU_createTestCase):

    person_dta = {
        'birth': OU_createTestCase.Cerebrum.Date(1970, 1, 1),
        'gender': OU_createTestCase.co.gender_male,
        'full_name': "Full Name",
        'address_text': 'adr',
        'postal_number': 'zip',
        'city': 'city'
        }

    def setUp(self):
        # print "Person_createTestCase.setUp()"
        # print "Type1: %s, type2: %s" % (type(Person_createTestCase),
        #                                 str(self))
        super(Person_createTestCase, self).setUp()
        new_person = Person.Person(self.Cerebrum)
        self._myPopulatePerson(new_person)
        new_person.write_db()
        self.person_id = new_person.entity_id

    def _myPopulatePerson(self, person):
        pd = self.person_dta
        person.populate(pd['birth'], pd['gender'])
        person.affect_names(self.co.system_manual, self.co.name_full)
        person.populate_name(self.co.name_full, pd['full_name'])
##         person.populate_external_id(co.system_manual,
##                                     co.externalid_fodselsnr, fnr)
        person.populate_address(self.co.system_manual,
                                self.co.address_post, address_text=pd['address_text'],
                                postal_number=pd['postal_number'], city=pd['city'])
        person.affect_affiliations(self.co.system_manual,
                                   self.co.affiliation_student)
        person.populate_affiliation(self.ou_id, self.co.affiliation_student,
                                    self.co.affiliation_status_student_valid)

    def tearDown(self):
        # print "Person_createTestCase.tearDown()"
        self.Cerebrum.execute("""
        DELETE FROM [:table schema=cerebrum name=person_affiliation]
        WHERE person_id=:id""", {'id': self.person_id})
        self.Cerebrum.execute("""
        DELETE FROM [:table schema=cerebrum name=person_name]
        WHERE person_id=:id""", {'id': self.person_id})
        self.Cerebrum.execute("""
        DELETE FROM [:table schema=cerebrum name=person_info]
        WHERE person_id=:id""", {'id': self.person_id})
        super(Person_createTestCase, self).tearDown()


class PersonTestCase(Person_createTestCase):

    def testCreatePerson(self):
        "Test that one can create a Person"
        self.failIf(getattr(self, "person_id", None) is None)

    def testComparePerson(self):
        "Check that created database object has correct values"
        person = Person.Person(self.Cerebrum)
        person.find(self.person_id)
        new_person = Person.Person(self.Cerebrum)
        new_person.clear()
        self._myPopulatePerson(new_person)
        if(new_person <> person):
            print "Error: should be equal"
        person.birth_date = self.person_dta['birth']
        person.gender = self.co.gender_female
        if new_person == person:
            print "Error: should be different"

    def testDeletePerson(self):
        "Delete the person"
        # This is actually a clean-up method, as we don't support
        # deletion of Persons
        self.tearDown()
        person = Person.Person(self.Cerebrum)
        self.assertRaises(Errors.NotFoundError, person.find, self.person_id)

    def suite():
        suite = unittest.TestSuite()
        suite.addTest(PersonTestCase("testCreatePerson"))
        suite.addTest(PersonTestCase("testComparePerson"))
        suite.addTest(PersonTestCase("testDeletePerson"))
        return suite
    suite = staticmethod(suite)


def suite():
    """Returns a suite containing all the test cases in this module.

    It can be a good idea to put an identically named factory function
    like this in every test module. Such a naming convention allows
    automation of test discovery.

    """

    suite1 = PersonTestCase.suite()
    return unittest.TestSuite((suite1,))


if __name__ == '__main__':
    # When executed as a script, perform all tests in suite().
    unittest.main(defaultTest='suite')
