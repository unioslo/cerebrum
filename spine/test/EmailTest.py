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

from omniORB import CORBA

import random
import unittest
from TestBase import *
import SpineIDL

class EmailDomainTest(SpineObjectTest):
    """Tests the e-mail module implementation in Spine."""
    def createObject(self):
        c = self.tr.get_commands()
        name = description = 'unittest_%s' % (id(self) + random.random())
        self.ed = c.create_email_domain(name, description)

    def deleteObject(self):
        pass # TODO: Find a way to delete the domains.

    def testSetName(self):
        ed_id = self.ed.get_id()
        name = self.ed.get_name()
        new_name = 'unittest_%s' % id(ed_id)
        self.ed.set_name(new_name)
        assert self.ed.get_name() == new_name 
        self.tr.commit()
        self.tr = self.session.new_transaction()
        self.ed = self.tr.get_email_domain(ed_id)
        assert self.ed.get_name() == new_name 
        self.ed.set_name(name)

    def testAddToCategory(self):
        ed_id = self.ed.get_id()
        s = self.tr.get_email_domain_category_searcher().search()
        assert len(s) # We need an e-mail domain category to run the test
        # Add the domain to the category
        edc = s[0]
        edc_id = edc.get_name()
        self.ed.add_to_category(edc)
        assert edc.get_id() in [i.get_id() for i in self.ed.get_categories()]
        self.tr.commit()

        # Check that the domain is in the category and remove it from the category
        self.tr = self.session.new_transaction()
        self.ed = self.tr.get_email_domain(ed_id)
        edc = self.tr.get_email_domain_category(edc_id)
        assert edc.get_id() in [i.get_id() for i in self.ed.get_categories()]
        self.ed.remove_from_category(edc)
        assert edc.get_id() not in [i.get_id() for i in self.ed.get_categories()]

    def testGetPersons(self):
        s = self.tr.get_person_affiliation_type_searcher()
        for aff_type in s.search():
            assert len(self.ed.get_persons(aff_type)) == 0

class EmailTargetTest(SpineObjectTest):
    def createObject(self):
        result = self.tr.get_email_target_type_searcher().search()
        assert len(result)
        self.et = self.tr.get_commands().create_email_target(result[0])
        self.et_id = self.et.get_id()

    def deleteObject(self):
        self.et.delete()

    def testType(self):
        ett_id = self.et.get_type().get_name()
        result = self.tr.get_email_target_type_searcher().search()
        for ett in result:
            if not self.et.get_type()._is_equivalent(ett):
                break
        else:
            assert 0 # We didn't find a type that wasn't already the type of the target we test

        # Set a new type and commit
        self.et.set_type(ett)
        new_ett_id = ett.get_name()
        assert self.et.get_type()._is_equivalent(ett)
        self.tr.commit()
        
        # Check that the new type was set, and reset it to the old type
        self.tr = self.session.new_transaction()
        self.et = self.tr.get_email_target(self.et_id)
        assert self.et.get_type().get_name() == new_ett_id
        ett = self.tr.get_email_target_type(ett_id)
        self.et.set_type(ett)
        assert self.et.get_type()._is_equivalent(ett)

    def testEntity(self):
        entity_id = self.et.get_entity()
        if entity_id is not None:
            entity_id = self.et.get_id()
        
        result = self.tr.get_account_searcher().search()
        assert len(result) # We need an account to perform the test
        searcher = self.tr.get_email_target_searcher()
        for account in result:
            if account.get_id() != entity_id:
                searcher.set_entity(account)
                if not len(searcher.search()):
                    break
        else:
            assert 0 # We didn't find any other accounts than the one that is already the target

        # Set a new entity
        new_entity_id = account.get_id()
        self.et.set_entity(account)
        assert self.et.get_entity() is not None and self.et.get_entity().get_id() == account.get_id()
        self.tr.commit()

        # Check that the new entity was set, and reset back to the old
        self.tr = self.session.new_transaction()
        self.et = self.tr.get_email_target(self.et_id)
        assert self.et.get_entity().get_id() == new_entity_id
        if entity_id is not None:
            account = self.tr.get_entity(entity_id)
        else:
            account = None
        self.et.set_entity(account)
        entity = self.et.get_entity()
        if entity is None:
            assert account is None
        else:
            assert entity._is_equivalent(account)

    def testAlias(self):
        alias = self.et.get_alias()
        new_alias = 'unittest_%s' % id(self.et)
        self.et.set_alias(new_alias)
        assert self.et.get_alias() == new_alias
        self.tr.commit()

        # Check that the alias was set, and reset to the old
        self.tr = self.session.new_transaction()
        self.et = self.tr.get_email_target(self.et_id)
        assert self.et.get_alias() == new_alias
        self.et.set_alias(alias)
        assert self.et.get_alias() == alias

    def testGetAddresses(self):
        assert len(self.et.get_addresses()) == 0

    def testGetPrimaryAddress(self):
        self.assertRaises(SpineIDL.Errors.NotFoundError, self.et.get_primary_address)

class EmailAddressTest(SpineObjectTest):
    def createObject(self):
        self._skip_different_primaries = False
        unique = 'unittest_%s' % (id(self.tr) + random.random())
        result = self.tr.get_email_domain_searcher().search()
        assert len(result) # We need a domain to perform the test
        domain = result[0]
        result = self.tr.get_email_target_searcher().search()
        assert len(result) # We need a target to perform the test
        for target in result:
            if len(target.get_addresses()):
                break
        else:
            self._skip_different_primaries = True
            target = result[0]
        self.ea = self.tr.get_commands().create_email_address(unique, domain, target)
        self.ea_id = self.ea.get_id()

    def deleteObject(self):
        self.ea.delete()

    def testSetAsPrimary(self):
        self.ea.set_as_primary()
        assert self.ea.is_primary()
        self.tr.commit()

        self.tr = self.session.new_transaction()
        self.ea = self.tr.get_email_address(self.ea_id)
        assert self.ea.is_primary()

        self.ea.unset_as_primary()
        assert not self.ea.is_primary()

    def testSetDifferentPrimaries(self):
        # Check if this test should be skipped
        # See also createObject()
        if self._skip_different_primaries:
            return

        # Find a second address for the target
        result = self.ea.get_target().get_addresses()
        for ea in result:
            if self.ea != ea:
                break
        else:
            assert 0 # Didn't find a second address that wasn't already a primary address
        ea.set_as_primary()
        assert ea.is_primary()
        assert not self.ea.is_primary()
        self.ea.set_as_primary()
        assert self.ea.is_primary()
        assert not ea.is_primary()

class EmailDomainCategorizationTest(SpineObjectTest):
    def createObject(self):
        pass
    def deleteObject(self):
        pass

    def testSanityOfGet(self):
        result = self.tr.get_email_domain_searcher().search()
        for ed in result:
            if len(ed.get_categories()):
                break
        else:
            assert 0 # We didn't find any domains with a category

        edc = ed.get_categories()[0]
        cat = self.tr.get_email_domain_categorization(ed, edc)
        assert cat.get_domain()._is_equivalent(ed)
        assert cat.get_category()._is_equivalent(edc)

if __name__ == '__main__':
    unittest.main()

# arch-tag: be0a2548-f9ef-11d9-9269-e389b52d4108
