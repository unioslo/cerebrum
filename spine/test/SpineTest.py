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
import unittest
from test import test_support

Errors = Spine.Cerebrum_core.Errors

def SpineConnection():
    """Returns a new connection to Spine."""
    return Spine.connect()

def SpineSession():
    """Creates a new session using the username and password from the configuration file."""
    spine = Spine.connect()
    user = Spine.config.get('spine', 'username')
    password = Spine.config.get('spine', 'password')
    return spine.login(user, password)

def SpineTransaction():
    """Grabs a new session and returns a new transaction."""
    session = SpineSession()
    return session.new_transaction()


class CommunicationTest(unittest.TestCase):
    """A simple test to verify that the Spine server is available and that CORBA is working."""

    def testConnect(self):
        """Test that we can connect and that we are connecting to Spine
        (unless someone spoofs our fancy version method)."""
        spine = SpineConnection()
        version = spine.get_version()
        assert type(version.major) is int and type(version.minor) is int


class TransactionTest(unittest.TestCase):
    def testRollback(self):
        """Open a transaction and rollback immediately."""
        transaction = SpineTransaction()
        transaction.rollback()

    def testCommit(self):
        """Open a transaction and commit immediately."""
        transaction = SpineTransaction()
        transaction.commit()

    def testRollbackWithoutChange(self):
        """Start a transaction, fetch a search object and rollback the transaction."""
        transaction = SpineTransaction()
        transaction.get_disk_searcher()
        transaction.rollback()

    def testCommitWithoutChange(self):
        """Start a transaction, fetch a search object and commit."""
        transaction = SpineTransaction()
        transaction.get_disk_searcher()
        transaction.commit()

    def testCommitWithChange(self):
        """Test that changes can be commited by setting a person name, commiting, setting the old name and commiting again."""
        transaction = SpineTransaction()
        person = transaction.get_person(90)
        name = person.get_names()[0]

        old_name = name.get_name()
        name.set_name('A testname')
        transaction.commit()

        transaction = SpineTransaction()
        person = transaction.get_person(90)
        name = person.get_names()[0]
        name.set_name(old_name)
        transaction.commit()

    def testTransactionsAndVerifyData(self):
        """Test that a change can be commited and verifies that the change is stored."""
        id = 35
        transaction = SpineTransaction()
        account = transaction.get_account(id)
        name = account.get_name()
        new_name = 'Test'
        account.set_name(new_name)
        transaction.commit()
        transaction = SpineTransaction()
        account = transaction.get_account(id)
        self.assertEquals(account.get_name(), new_name)
        account.set_name(name)
        transaction.commit()
        transaction = SpineTransaction()
        account = transaction.get_account(id)
        self.assertEquals(account.get_name(), name)


class LockingTest(unittest.TestCase):
    def testReadLockWithRead(self):
        """Verify the read lock implementation by read-locking an object and then read-locking the object from another transaction."""
        id = 35
        transaction_1 = SpineTransaction()
        transaction_2 = SpineTransaction()

        account_1 = transaction_1.get_account(id)
        account_2 = transaction_1.get_account(id)

        account_1.get_name()
        account_2.get_name()

        transaction_1.rollback()
        transaction_2.rollback()

    def testReadLockWithWrite(self):
        """Verify the read lock implementation by read-locking an object and then write-locking the object from another transaction."""
        id = 35
        transaction_1 = SpineTransaction()
        transaction_2 = SpineTransaction()

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
        transaction_1 = SpineTransaction()
        transaction_2 = SpineTransaction()

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
        transaction_1 = SpineTransaction()
        transaction_2 = SpineTransaction()

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
        transaction_1 = SpineTransaction()
        transaction_2 = SpineTransaction()
        account_35 = transaction_1.get_account(35)
        account_117 = transaction_2.get_account(117)
        name_35 = account_35.get_name()
        name_117 = account_117.get_name()
        account_35.set_name(test_name)
        account_117.set_name(test_name)
        transaction_1.commit()
        transaction_2.commit()
        transaction_1 = SpineTransaction()
        transaction_2 = SpineTransaction()
        account_35 = transaction_1.get_account(35)
        account_117 = transaction_1.get_account(117)
        self.assertEquals(account_35.get_name(), test_name)
        self.assertEquals(account_117.get_name(), test_name)
        account_35.set_name(name_35)
        account_117.set_name(name_117)
        transaction_1.commit()
        transaction_2.commit()
        transaction_1 = SpineTransaction()
        transaction_2 = SpineTransaction()
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
        transaction_1 = SpineTransaction()
        transaction_2 = SpineTransaction()
        account_1 = transaction_1.get_account(id)
        account_2 = transaction_2.get_account(id)
        name_1 = account_1.get_name()
        name_2 = account_2.get_name()
        self.assertEquals(name_1, name_2)
        transaction_2.commit()

        account_1.set_name(test_name)
        transaction_2 = SpineTransaction()
        account_2 = transaction_2.get_account(id)

        self.assertRaises(Errors.AlreadyLockedError, account_2.get_name)
        
        transaction_1.commit()
        transaction_1 = SpineTransaction()
        account_1 = transaction_1.get_account(id)

        account_2.set_name(test_name2)

        self.assertRaises(Errors.AlreadyLockedError, account_1.get_name)

        self.assertEquals(account_2.get_name(), test_name2)
        transaction_2.commit()

        self.assertEquals(account_1.get_name(), test_name2)
        account_1.set_name(name_1)
        transaction_1.commit()

        transaction_1 = SpineTransaction()
        account_1 = transaction_1.get_account(id)
        self.assertEquals(account_1.get_name(), name_1)
        transaction_1.rollback()

        transaction.rollback()


if __name__ == '__main__':
    test_support.run_unittest(CommunicationTest,
        TransactionTest, LockingTest, MultipleTransactionTest)

# arch-tag: d4e71fa7-90e0-4fd5-8b38-ce5ac0340e2f
