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

import cStringIO
import unittest
from test import test_support
from TestBase import *
import SpineIDL

__all__ = []

untestable_classes = ['get_account_view_searcher']
untestable_cls_methods = [
    ('get_ou_searcher', 'get_parent'), 
    ('get_ou_searcher', 'get_children'), 
    ('get_ou_searcher', 'get_entity_name'),
    ('get_ou_searcher', 'get_external_id'),
    ('get_person_searcher', 'get_entity_name'), 
    ('get_person_searcher', 'get_email_domain'),
    ('get_person_searcher', 'get_external_id'),
    ('get_group_searcher', 'get_entity_name'),
    ('get_group_searcher', 'get_external_id'),
    ('get_account_searcher', 'get_entity_name'), 
    ('get_account_searcher', 'get_external_id'),
    ('get_email_domain_searcher', 'get_persons'), 
    ('get_group_searcher', 'get_address'),
    ('get_person_searcher', 'get_address'),
    ('get_account_searcher', 'get_address'),
    ('get_group_searcher', 'get_quarantine'),
    ('get_person_searcher', 'get_quarantine'),
    ('get_account_searcher', 'get_quarantine'),
    ('get_account_searcher', 'get_homedir'),
]
untestable_methods = [
    'get_quarantine',
    'get_entity_name',
    'get_contact_info',
    'get_external_id',
    'get_address'
]

log = cStringIO.StringIO()

def _create_testclass_namespace(cls_name):
    exec 'class Test%s(unittest.TestCase):\n pass\ntestclass=Test%s' % (cls_name[4:-9], cls_name[4:-9]) # Remove get_ and _searcher from the test name
    return testclass

def _create_testclass_base(cls_name):
    """Creates a new test class which is ready for method addition."""
    testclass = _create_testclass_namespace(cls_name)
    def setUp(self):
        self.session = spine.login(username, password)
        self.transaction = self.session.new_transaction()
        self.search_obj = getattr(self.transaction, cls_name)()
        self.obj = self.search_obj.search()[0]
    testclass.setUp = setUp

    def tearDown(self):
        self.transaction.rollback()
        self.session.logout()
    testclass.tearDown = tearDown

    def testSearchObject(self):
        """Tests that getting any attribute on a fresh search object raises a
        proper exception."""
        for attr in dir(self.search_obj):
            if attr.startswith('get_') and not attr in ['get_dumpers', 'get_search_objects']:
                self.assertRaises(SpineIDL.Errors.ClientProgrammingError, getattr(self.search_obj, attr))
    testclass.testSearchObject = testSearchObject

    def testDump(self):
        """Tests that a %s dump works.""" % self.obj.__class__.__name__
        if not hasattr(self.search_obj, 'get_dumper'):
            return
        dumper = self.search_obj.get_dumper()
        for attr in dir(dumper):
            if attr.startswith('mark'):
                try:
                    getattr(dumper, attr)()
                except SpineIDL.Errors.NotFoundError:
                    print >> log, 'Note: Test of dump, mark method %s, did not have the required data.' % (attr)
        for obj in dumper.dump():
            for attr in dir(obj):
                if not attr.startswith('_'):
                    getattr(obj, attr) # just access them to see that it works
    testclass.testDump = testDump

    return testclass

def _create_testmethod(method_name):
    """
    Creates a new test method that tests a given method name in
    a given class. The returned method is ready for being added
    to a class as an unbound method.

    Arguments:
        method_name - the method for which the test method should 
        be generated.
    """
    def test(self):
        """Tests %s on %s""" % (method_name, self.obj.__class__.__name__)
        try:
            getattr(self.obj, method_name)()
        except SpineIDL.Errors.NotFoundError: # If we don't have data available, the test shouldn't fail
            print >> log, 'Note: Test on %s did not have the required data.' % (method_name)
    return test

def _create_testclass(cls, obj):
    """
    Creates a test class from the given constructor method and
    object reference.
    
    Arguments:
        cls - the constructor method for the class
        obj - an object of the class
    """

    testclass = _create_testclass_base(cls)
    for attr in dir(obj):
        if not attr.startswith('get') or not callable(getattr(obj, attr)) or attr in untestable_methods or (cls, attr) in untestable_cls_methods:
            continue
        setattr(testclass, 'test_%s' % attr, _create_testmethod(attr))
        method = getattr(testclass, 'test_%s' % attr)
    return testclass

def create_test_classes():
    """Creates all test classes for testing the Spine objects."""

    session = spine.login(username, password)
    transaction = session.new_transaction()
    testclasses = list()
    
    # Loop through all attributes and prepare objects
    for attr in dir(transaction):
        transaction = session.new_transaction()
        if attr.startswith('get_') and attr.endswith('_searcher') and not attr in untestable_classes:
            cls = getattr(transaction, attr)
            try:
                objects = cls().search()
            except:
                print 'Error: Search failed on \'%s\', unable to generate test.' % attr[4:-9] # Name without get_ and _searcher
                traceback.print_exc()
            if len(objects):
                obj = objects[0]
                tc = _create_testclass(attr, obj)
                testclasses.append(tc)
                globals()[obj.__class__.__name__] = tc
                __all__.append(obj.__class__.__name__)
            else:
                print 'Note: No instances of \'%s\' available in database.' % attr[4:-9] # Name without get_ and _searcher
        transaction.rollback()
    session.logout()

print 'Generating test suites...'
create_test_classes()
print 'Test suites generated.'

if __name__ == '__main__':
    try:
        unittest.main()
    except SystemExit:
        l = log.getvalue()
        if len(l):
            print 'Contents of automated testsuite log:'
            print l

# arch-tag: 828dc5da-e7d7-11d9-90e8-671c7cd91ff4
