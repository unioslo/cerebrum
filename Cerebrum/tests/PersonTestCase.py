#!/usr/bin/env python2.2
#
# $Id$

import unittest
from Cerebrum import Database
from Cerebrum import OU
from Cerebrum import Person
from Cerebrum import Account
from Cerebrum import Constants

from Cerebrum.tests.OUTestCase import OU_createTestCase

class Person_createTestCase(OU_createTestCase):

    person_dta = {
        'birth': OU_createTestCase.Cerebrum.Date(1970, 1, 1),
        'gender' : OU_createTestCase.co.gender_male,
        'full_name': "Full Name",
        'adr': 'adr', 'zip': 'zip', 'city': 'city'
        }

    def setUp(self):
        # print "Person_createTestCase.setUp()"
        # print "Type1: %s, type2: %s" % (type(Person_createTestCase), str(self))
        super(Person_createTestCase, self).setUp()
        new_person = Person.Person(self.Cerebrum)
        self._myPopulatePerson(new_person)
        new_person.write_db()
        self.person_id = new_person.person_id

    def _myPopulatePerson(self, person):
        pd = self.person_dta

        person.populate(pd['birth'], pd['gender'])
        person.affect_names(self.co.system_fs, self.co.name_full)
        person.populate_name(self.co.name_full, pd['full_name'])

        # person.populate_external_id(co.system_fs, co.externalid_fodselsnr, fnr)

        person.affect_addresses(self.co.system_fs, self.co.address_post)
        person.populate_address(self.co.address_post, addr=pd['adr'],
                                    zip=pd['zip'],
                                    city=pd['city'])
        person.affect_affiliations(self.co.system_fs, self.co.affiliation_student)
        person.populate_affiliation(self.ou_id, self.co.affiliation_student,
                                        self.co.affiliation_status_student_valid)

    def tearDown(self):
        # print "Person_createTestCase.tearDown()"
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
        person.populate(self.person_dta['birth'], self.co.gender_female)
        if(new_person == person):
            print "Error: should be different"

    def testDeletePerson(self):
        "Delete the person"
        # This is actually a clean-up method, as we don't support deletion of Persons
        self.Cerebrum.execute(
            """DELETE FROM [:table schema=cerebrum name=person_affiliation]
               WHERE person_id=:id""", {'id': self.person_id})
        self.Cerebrum.execute(
            """DELETE FROM [:table schema=cerebrum name=person_name]
               WHERE person_id=:id""", {'id': self.person_id})
        self.Cerebrum.execute(
            """DELETE FROM [:table schema=cerebrum name=person_info]
               WHERE person_id=:id""", {'id': self.person_id})
        person = Person.Person(self.Cerebrum)
        try:
            person.find(self.person_id)
            fail("Error: Should no longer exist")
        except:
            # OK
            pass

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
    # When this module is executed from the command-line, run all its tests
    unittest.main(defaultTest='suite')
