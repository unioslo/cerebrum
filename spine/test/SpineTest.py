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

import Spine
import SpineHelper
import traceback
import unittest
from test import test_support

Errors = Spine.Cerebrum_core.Errors

class CommunicationTest(unittest.TestCase):
    """A simple test to verify that the Spine server is available and that CORBA is working."""

    def testConnect(self):
        """Test that we can connect and that we are connecting to Spine
        (unless someone spoofs our fancy version method)."""
        spine = SpineHelper.Connection()
        version = spine.get_version()
        assert type(version.major) is int and type(version.minor) is int

class TransactionTest(unittest.TestCase):
    def testRollback(self):
        """Open a transaction and rollback immediately."""
        transaction = SpineHelper.Transaction()
        transaction.rollback()

    def testCommit(self):
        """Open a transaction and commit immediately."""
        transaction = SpineHelper.Transaction()
        transaction.commit()

    def testRollbackWithoutChange(self):
        """Start a transaction, fetch a search object and rollback the transaction."""
        transaction = SpineHelper.Transaction()
        transaction.get_disk_searcher()
        transaction.rollback()

    def testCommitWithoutChange(self):
        """Start a transaction, fetch a search object and commit."""
        transaction = SpineHelper.Transaction()
        transaction.get_disk_searcher()
        transaction.commit()

    def testCommitWithChange(self):
        """Test that changes can be commited by setting a person name, commiting, setting the old name and commiting again."""
        transaction = SpineHelper.Transaction()
        person = transaction.get_person(90)
        name = person.get_names()[0]

        old_name = name.get_name()
        name.set_name('A testname')
        transaction.commit()

        transaction = SpineHelper.Transaction()
        person = transaction.get_person(90)
        name = person.get_names()[0]
        name.set_name(old_name)
        transaction.commit()

    def testTransactionsAndVerifyData(self):
        """Test that a change can be commited and verifies that the change is stored."""
        id = 35
        transaction = SpineHelper.Transaction()
        account = transaction.get_account(id)
        name = account.get_name()
        new_name = 'Test'
        account.set_name(new_name)
        transaction.commit()
        transaction = SpineHelper.Transaction()
        account = transaction.get_account(id)
        self.assertEquals(account.get_name(), new_name)
        account.set_name(name)
        transaction.commit()
        transaction = SpineHelper.Transaction()
        account = transaction.get_account(id)
        self.assertEquals(account.get_name(), name)


class LockingTest(unittest.TestCase):
    def testReadLockWithRead(self):
        """Verify the read lock implementation by read-locking an object and then read-locking the object from another transaction."""
        id = 35
        transaction_1 = SpineHelper.Transaction()
        transaction_2 = SpineHelper.Transaction()

        account_1 = transaction_1.get_account(id)
        account_2 = transaction_1.get_account(id)

        account_1.get_name()
        account_2.get_name()

        transaction_1.rollback()
        transaction_2.rollback()

    def testReadLockWithWrite(self):
        """Verify the read lock implementation by read-locking an object and then write-locking the object from another transaction."""
        id = 35
        transaction_1 = SpineHelper.Transaction()
        transaction_2 = SpineHelper.Transaction()

        account_1 = transaction_1.get_account(id)
        account_2 = transaction_2.get_account(id)

        account_1.get_name()
        self.assertRaises(Errors.AlreadyLockedError, account_2.set_name, 'Test')

        transaction_1.rollback()
        account_2.set_name('Test')
        transaction_2.rollback()

    def testWriteLockWithRead(self):
        """Confirm that it's impossible to get a read lock on an already write-locked object."""
        id = 35
        transaction_1 = SpineHelper.Transaction()
        transaction_2 = SpineHelper.Transaction()

        account_1 = transaction_1.get_account(id)
        account_2 = transaction_2.get_account(id)

        account_1.set_name('test')
        self.assertRaises(Errors.AlreadyLockedError, account_2.get_name)

        transaction_1.rollback()
        account_1.get_name()
        transaction_2.rollback()

    def testWriteLockWithWrite(self):
        """Confirm that it's impossible to get a write lock on an already write-locked object."""
        id = 35
        transaction_1 = SpineHelper.Transaction()
        transaction_2 = SpineHelper.Transaction()

        account_1 = transaction_1.get_account(id)
        account_2 = transaction_2.get_account(id)

        account_1.set_name('test')
        self.assertRaises(Errors.AlreadyLockedError, account_2.set_name, 'test')

        transaction_1.rollback()
        account_2.set_name('test')
        transaction_2.rollback()


class MultipleTransactionTest(unittest.TestCase):
    def testMultipleTransactionsWithDifferentObjects(self):
        """Test multiple transaction manipulating different objects (commiting changes and verifying that they were written to the database)."""
        id_1 = 35
        id_2 = 117
        test_name = 'test'
        transaction_1 = SpineHelper.Transaction()
        transaction_2 = SpineHelper.Transaction()
        account_35 = transaction_1.get_account(35)
        account_117 = transaction_2.get_account(117)
        name_35 = account_35.get_name()
        name_117 = account_117.get_name()
        account_35.set_name(test_name)
        account_117.set_name(test_name)
        transaction_1.commit()
        transaction_2.commit()
        transaction_1 = SpineHelper.Transaction()
        transaction_2 = SpineHelper.Transaction()
        account_35 = transaction_1.get_account(35)
        account_117 = transaction_1.get_account(117)
        self.assertEquals(account_35.get_name(), test_name)
        self.assertEquals(account_117.get_name(), test_name)
        account_35.set_name(name_35)
        account_117.set_name(name_117)
        transaction_1.commit()
        transaction_2.commit()
        transaction_1 = SpineHelper.Transaction()
        transaction_2 = SpineHelper.Transaction()
        account_35 = transaction_1.get_account(35)
        account_117 = transaction_2.get_account(117)
        self.assertEquals(account_35.get_name(), name_35)
        self.assertEquals(account_117.get_name(), name_117)
        transaction_1.rollback()
        transaction_2.rollback()

    def testMultipleTransactionsWithSameObjects(self):
        """Test multiple transactions operating on the same object (verifies that locking works as expected)."""
        id = 35
        test_name = 'test'
        test_name = 'test2'
        transaction_1 = SpineHelper.Transaction()
        transaction_2 = SpineHelper.Transaction()
        account_1 = transaction_1.get_account(id)
        account_2 = transaction_2.get_account(id)
        name_1 = account_1.get_name()
        name_2 = account_2.get_name()
        self.assertEquals(name_1, name_2)
        transaction_2.commit()

        account_1.set_name(test_name)
        transaction_2 = SpineHelper.Transaction()
        account_2 = transaction_2.get_account(id)

        self.assertRaises(Errors.AlreadyLockedError, account_2.get_name)
        
        transaction_1.commit()
        transaction_1 = SpineHelper.Transaction()
        account_1 = transaction_1.get_account(id)

        account_2.set_name(test_name2)

        self.assertRaises(Errors.AlreadyLockedError, account_1.get_name)

        self.assertEquals(account_2.get_name(), test_name2)
        transaction_2.commit()

        self.assertEquals(account_1.get_name(), test_name2)
        account_1.set_name(name_1)
        transaction_1.commit()

        transaction_1 = SpineHelper.Transaction()
        account_1 = transaction_1.get_account(id)
        self.assertEquals(account_1.get_name(), name_1)
        transaction_1.rollback()

        transaction.rollback()

# Below here are a bunch of hacky functions that collaborate
# to create a set of unit tests in a sort of generic manner. ;)

def _create_testclass_namespace():
    """Creates a new empty class namespace for a test class."""
    class TestClass(unittest.TestCase):
        pass
    return TestClass

def _create_testclass_base(cls_name):
    """Creates a new test class which is ready for method addition."""
    testclass = _create_testclass_namespace()
    def setUp(self):
        self.transaction = SpineHelper.Transaction()
        self.search = getattr(self.transaction, cls_name)()
        self.obj = self.search.search()[0]
    testclass.setUp = setUp

    def tearDown(self):
        self.transaction.rollback()
    testclass.tearDown = tearDown

    def testDump(self):
        """Test that the class dump works if present."""
        if not hasattr(self.search, 'get_dumper'):
            return
        dumper = self.search.get_dumper()
        for attr in dir(dumper):
            if attr.startswith('mark'):
                getattr(dumper, attr)()
        for obj in dumper.dump():
            for attr in dir(obj):
                if not attr.startswith('_'):
                    getattr(obj, attr) # just access them
    testclass.testDump = testDump

    return testclass

def _create_testmethod(method_name):
    """Creates a new test method that tests a given method name in
    a given class. The returned method is ready for being added
    to a class as an unbound method.

    Arguments:
        method_name - the method for which the test method should 
        be generated.
    """
    def test(self):
        """Calls method %s on %s.""" % (method_name, self.obj.__class__.__name__)
        getattr(self.obj, method_name)()
    return test

def _create_testclass(cls, obj):
    """Creates a test class from the given constructor method and
    object reference.
    
    Arguments:
        cls - the constructor method for the class
        obj - an object of the class (to be used when testing)."""

    print '>>> Class %s' % obj.__class__.__name__
    testclass = _create_testclass_base(cls)
    for j in dir(obj):
        if not j.startswith('get') or not callable(getattr(obj, j)):
            continue
        setattr(testclass, 'test_%s' % j, _create_testmethod(j))
        print '... method %s()' % j
    return testclass

def create_test_classes():
    """Creates all test classes for testing the Spine objects."""

    transaction = SpineHelper.Transaction()
    testclasses = list()
    
    # Loop through all attributes and prepare objects
    for attr in dir(transaction):
        if attr.startswith('get_') and attr.endswith('_searcher'):
            cls = getattr(transaction, attr)
            try:
                objects = cls().search()
            except:
                print 'Error: Search failed on %s, unable to generate test.' % attr[4:-9]
                traceback.print_exc()
            try:
                obj = objects[0]
                testclasses.append(_create_testclass(attr, obj))
            except IndexError:
                print 'Error: No test data for %s.' % attr[4:-9]
    return testclasses

if __name__ == '__main__':

    # Create the unit tests and add the pre-defined ones
    classes = [CommunicationTest, TransactionTest, LockingTest, 
        MultipleTransactionTest] + create_test_classes()
    test_support.run_unittest(*classes)

# arch-tag: d4e71fa7-90e0-4fd5-8b38-ce5ac0340e2f
