#!/usr/bin/env python
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
import cereconf
from Cerebrum import Errors
from Cerebrum.Entity import \
     Entity, EntityName, EntityContactInfo, EntityAddress
from Cerebrum.Utils import Factory
from Cerebrum import Constants
import traceback


# We want new-style classes.  To make a new-style subclass of an
# old-style class like unittest.TestCase, we append `object` to the
# subclass's base class list.
class Entity_createTestCase(unittest.TestCase, object):

    Cerebrum = Factory.get('Database')()
    Cerebrum.cl_init(change_program="EntityTestCase")
    co = Factory.get('Constants')(Cerebrum)
    entity_class = Entity

    def _myPopulateEntity(self, e):
        e.populate(self.co.entity_ou)

    def setUp(self):
        try:
            entity = self.entity_class(self.Cerebrum)
            self._myPopulateEntity(entity)
            entity.write_db()
            self.entity_id = int(entity.entity_id)
            self.entity = entity
        except:
            print "Error: unable to create entity"
            traceback.print_exc()
            raise

    def tearDown(self):
        # print "Account_createTestCase.tearDown()"
        self.Cerebrum.execute("""
        DELETE FROM [:table schema=cerebrum name=entity_info]
        WHERE entity_id=:id""", {'id': self.entity_id})
        self.Cerebrum.commit()


class EntityTestCase(Entity_createTestCase):
    def testCreateEntity(self):
        "Test that one can create an Entity"
        self.failIf(not hasattr(self, "entity_id"))

    def testCompareEntity(self):
        "Check that created database object has correct values"
        entity = self.entity_class(self.Cerebrum)
        entity.find(self.entity_id)
        new_entity = self.entity_class(self.Cerebrum)
        self._myPopulateEntity(new_entity)

        self.failIf(new_entity <> entity, "Error: should be equal")
##         new_entity.entity_type = 'foobar' # TBD: Is this even legal?
##         self.failIf(new_entity == entity,
##                     "Error: should be different if it is legal to"
##                     " change entity_type")

    def testDeleteEntity(self):
        "Delete the Entity"
        # This is actually a clean-up method, as we don't support
        # deletion of Entities
        self.tearDown()
        entity = self.entity_class(self.Cerebrum)
        self.assertRaises(Errors.NotFoundError, entity.find, self.entity_id)

    def suite():
        suite = unittest.TestSuite()
        suite.addTest(EntityTestCase("testCreateEntity"))
        suite.addTest(EntityTestCase("testCompareEntity"))
        suite.addTest(EntityTestCase("testDeleteEntity"))
        return suite
    suite = staticmethod(suite)


class EntityName_createTestCase(Entity_createTestCase):
    entity_class = EntityName
    test_name = "foobar3"

    def setUp(self):
        super(EntityName_createTestCase, self).setUp()
        try:
            self.entity.add_entity_name(self.co.account_namespace, self.test_name)
        except:
            print "Error: unable to create EntityName"
            traceback.print_exc()
            raise

    def tearDown(self):
        self.entity.delete_entity_name(self.co.account_namespace)
        super(EntityName_createTestCase, self).tearDown()

class EntityNameTestCase(EntityName_createTestCase):
    def testEntityGetName(self):
        "Test that one can get the created EntityName"
        name = self.entity.get_name(self.co.account_namespace)
        self.failIf(name <> self.test_name,
                    "EntityNames should be equal")

    def testEntityFindByName(self):
        "Test that one can find an entity by name"
        old_id = self.entity_id
        self.entity.clear()
        self.entity.find_by_name(self.test_name, self.co.account_namespace)
        self.failIf(self.entity_id <> old_id,
                    "EntityNames entity_id should be equal")

    def testEntityDeleteName(self):
        "Test that the EntityName can be deleted"
        self.entity.delete_entity_name(self.co.account_namespace)
        self.assertRaises(Errors.NotFoundError,
                          self.entity.get_name, self.co.account_namespace)

    def suite():
        suite = unittest.TestSuite()
        suite.addTest(EntityNameTestCase("testEntityGetName"))
        suite.addTest(EntityNameTestCase("testEntityFindByName"))
        suite.addTest(EntityNameTestCase("testEntityDeleteName"))
        return suite
    suite = staticmethod(suite)


class EntityContactInfo_createTestCase(Entity_createTestCase):
    entity_class = EntityContactInfo
    test_ci = {'src': 'system_manual', 'type': 'contact_phone',
               'pref': 10, 'value': '+47 12345678',
               'desc': 'some description'}

    def setUp(self):
        super(EntityContactInfo_createTestCase, self).setUp()
        try:
            for k in ('src', 'type'):
                if isinstance(self.test_ci[k], str):
                    self.test_ci[k] = getattr(self.co, self.test_ci[k])
            self.entity.add_contact_info(self.test_ci['src'],
                                         self.test_ci['type'],
                                         self.test_ci['value'],
                                         self.test_ci['pref'],
                                         self.test_ci['desc'])
        except:
            print "Error: unable to create EntityContactInfo"
            traceback.print_exc()
            raise

    def tearDown(self):
        self.entity.delete_contact_info(self.test_ci['src'],
                                        self.test_ci['type'])
        super(EntityContactInfo_createTestCase, self).tearDown()

class EntityContactInfoTestCase(EntityContactInfo_createTestCase):
    def testEntityGetContactInfo(self):
        "Test that one can get the created EntityContactInfo"
        ci = self.entity.get_contact_info(self.test_ci['src'],
                                          self.test_ci['type'])
        ci = ci[0]
        self.failIf(ci['contact_value'] <> self.test_ci['value'] or \
                    ci['description'] <> self.test_ci['desc'],
                    "EntityContactInfo should be equal")

    def testEntityDeleteContactInfo(self):
        "Test that the EntityContactInfo can be deleted"
        self.entity.delete_contact_info(self.test_ci['src'],
                                        self.test_ci['type'])
        self.failIf(self.entity.get_contact_info(self.test_ci['src'],
                                                 self.test_ci['type']),
                    "EntityContactInfo won't go away.")

    def suite():
        suite = unittest.TestSuite()
        suite.addTest(EntityContactInfoTestCase("testEntityGetContactInfo"))
        suite.addTest(EntityContactInfoTestCase("testEntityDeleteContactInfo"))
        return suite
    suite = staticmethod(suite)


class EntityAddress_createTestCase(Entity_createTestCase):
    entity_class = EntityAddress
    test_a = {'src': 'system_manual',
              'type': 'address_post',
              'address_text': 'some address',
              'p_o_box': 'some pb',
              'postal_number': 'some pn',
              'city': 'some city',
              'country': None}

    def setUp(self):
        super(EntityAddress_createTestCase, self).setUp()
        try:
            for k in ('src', 'type'):
                if isinstance(self.test_a[k], str):
                    self.test_a[k] = getattr(self.co, self.test_a[k])
            self.entity.add_entity_address(self.test_a['src'],
                                           self.test_a['type'],
                                           self.test_a['address_text'],
                                           self.test_a['p_o_box'],
                                           self.test_a['postal_number'],
                                           self.test_a['city'],
                                           self.test_a['country'])
        except:
            print "Error: unable to create EntityAddress"
            traceback.print_exc()
            raise

    def tearDown(self):
        self.entity.delete_entity_address(self.test_a['src'],
                                          self.test_a['type'])
        super(EntityAddress_createTestCase, self).tearDown()

class EntityAddressTestCase(EntityAddress_createTestCase):
    def testEntityGetAddress(self):
        "Test that one can get the created EntityAddress"
        addr = self.entity.get_entity_address(self.test_a['src'],
                                              self.test_a['type'])
        addr = addr[0]
        self.failIf(addr['address_text'] <> self.test_a['address_text'] or
                    addr['p_o_box'] <> self.test_a['p_o_box'] or
                    addr['postal_number'] <> self.test_a['postal_number'] or
                    addr['city'] <> self.test_a['city'],
                    "EntityAddress should be equal")

    def testEntityDeleteAddress(self):
        "Test that the EntityAddress can be deleted"
        self.entity.delete_entity_address(self.test_a['src'],
                                          self.test_a['type'])
        self.failIf(self.entity.get_entity_address(self.test_a['src'],
                                                   self.test_a['type']),
                    "EntityAddress won't go away.")

    def suite():
        suite = unittest.TestSuite()
        suite.addTest(EntityAddressTestCase("testEntityGetAddress"))
        suite.addTest(EntityAddressTestCase("testEntityDeleteAddress"))
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
    suite3 = EntityContactInfoTestCase.suite()
    suite4 = EntityAddressTestCase.suite()

    return unittest.TestSuite((suite1, suite2, suite3, suite4))


if __name__ == '__main__':
    # When this module is executed from the command-line, run all its tests
    unittest.main(defaultTest='suite')

# arch-tag: a8757454-083c-43da-af74-d6ec784759cc
