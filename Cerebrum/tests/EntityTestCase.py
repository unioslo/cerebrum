#!/usr/bin/env python2.2
#
# $Id$

import unittest
from Cerebrum import Database
from Cerebrum.Entity import \
     Entity, EntityName
from Cerebrum import Constants
from Cerebrum import cereconf
import traceback

from Cerebrum.tests.PersonTestCase import Person_createTestCase

class Entity_createTestCase(unittest.TestCase, object, Entity):
    Cerebrum = Database.connect()
    co = Constants.Constants(Cerebrum)

    def _myPopulateEntity(self, e):
        e.populate(self.co.entity_ou)
    
    def setUp(self):
        super(Entity, self).__init__(self.Cerebrum)  # EntityName needs this
        
        entity = None
        try:
            entity = Entity(self.Cerebrum)
            self._myPopulateEntity(entity)
            entity.write_db()
        except:
            print "Error: unable to create entity"
            traceback.print_exc()            
        self.entity_id = int(entity.entity_id)

    def tearDown(self):
        # print "Account_createTestCase.tearDown()"
        self.Cerebrum.execute(
            """DELETE FROM [:table schema=cerebrum name=entity_info]
               WHERE entity_id=:id""", {'id': self.entity_id})

class EntityTestCase(Entity_createTestCase):
    def testCreateEntity(self):
        "Test that one can create an Entity"
        self.failIf(getattr(self, "entity_id", None) is None)

    def testCompareEntity(self):
        "Check that created database object has correct values"
        entity = Entity(self.Cerebrum)
        entity.find(self.entity_id)
        new_entity = Entity(self.Cerebrum)
        self._myPopulateEntity(new_entity)

        self.failIf(new_entity <> entity, "Error: should be equal")
        new_entity.entity_type = 'foobar'  # TBD: Is this even legal?
        self.failIf(new_entity == entity, "Error: should be different if it is legal to change entity_type")

    def testDeleteEntity(self):
        "Delete the person"
        # This is actually a clean-up method, as we don't support deletion of Entities
        self.tearDown()
        entity = Entity(self.Cerebrum)
        try:
            entity.find(self.entity_id)
            fail("Error: Should no longer exist")
        except:
            # OK
            pass

    def suite():
        suite = unittest.TestSuite()
        suite.addTest(EntityTestCase("testCreateEntity"))
        suite.addTest(EntityTestCase("testCompareEntity"))
        suite.addTest(EntityTestCase("testDeleteEntity"))
        return suite
    suite = staticmethod(suite)


class EntityName_createTestCase(Entity_createTestCase, EntityName):
    test_name = "foobar3"
    def setUp(self):
        super(EntityName_createTestCase, self).setUp()
        self.add_name(self.co.account_namespace, self.test_name)

    def tearDown(self):
        self.delete_name(self.co.account_namespace)
        super(EntityName_createTestCase, self).tearDown()

class EntityNameTestCase(EntityName_createTestCase):
    def testEntityGetName(self):
        "Test that one can get the created EntityName"

        name = self.get_name(self.co.account_namespace)
        self.failIf(name.entity_name <> self.test_name, "EntityNames should be equal")

    def testEntityFindByName(self):
        "Test that one can find an entity by name"
        
        old_id = self.entity_id
        self.find_by_name(self.co.account_namespace, self.test_name)
        self.failIf(self.entity_id <> old_id, "EntityNames entity_id should be equal")

    def testEntityDeleteName(self):
        "Test that the EntityName can be deleted"
        
        self.delete_name(self.co.account_namespace)
        try:
            self.get_name(self.co.account_namespace)
            fail("Error: should no longer exist")
        except:
            pass

    def suite():
        suite = unittest.TestSuite()
        suite.addTest(EntityNameTestCase("testEntityGetName"))
        suite.addTest(EntityNameTestCase("testEntityFindByName"))
        suite.addTest(EntityNameTestCase("testEntityDeleteName"))
        return suite
    suite = staticmethod(suite)

def suite():
    """Returns a suite containing all the test cases in this module.
       It can be a good idea to put an identically named factory function
       like this in every test module. Such a naming convention allows
       automation of test discovery.
    """

    suite1 = EntityTestCase.suite()
    suite2 = EntityNameTestCase.suite()

    return unittest.TestSuite((suite1, suite2))


if __name__ == '__main__':
    # When this module is executed from the command-line, run all its tests
    unittest.main(defaultTest='suite')
