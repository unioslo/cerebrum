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

import unittest
from TestBase import *

class LockingTest(unittest.TestCase):
    def setUp(self):
        self.session = spine.login(username, password)
    def tearDown(self):
        self.session.logout()
    def testReadLockWithRead(self):
        """Verify the read lock implementation by read-locking an object and
        then read-locking the object from another transaction."""
        transaction_1 = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 1
        transaction_2 = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 2

        account_1 = transaction_1.get_account_searcher().search()[0]
        account_2 = transaction_2.get_account(account_1.get_id())

        name_1 = account_1.get_name()
        name_2 = account_2.get_name()
        assert name_1 == name_2

        assert len(self.session.get_transactions()) == 2
        transaction_1.rollback()
        assert len(self.session.get_transactions()) == 1
        transaction_2.rollback()
        assert len(self.session.get_transactions()) == 0

    def testReadLockWithWrite(self):
        """Verify the read lock implementation by read-locking an object and
        then write-locking the object from another transaction."""
        transaction_1 = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 1
        transaction_2 = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 2

        account_1 = transaction_1.get_account_searcher().search()[0]
        account_2 = transaction_2.get_account(account_1.get_id())

        account_1.get_name()
        self.assertRaises(Spine.Errors.AlreadyLockedError, account_2.set_name, 'Test')

        transaction_1.rollback()
        assert len(self.session.get_transactions()) == 1
        account_2.set_name('Test')
        transaction_2.rollback()
        assert len(self.session.get_transactions()) == 0

    def testWriteLockWithRead(self):
        """Confirm that it's impossible to get a read lock on an already
        write-locked object."""
        transaction_1 = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 1
        transaction_2 = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 2

        account_1 = transaction_1.get_account_searcher().search()[0]
        account_1.set_name('Test')
        account_2 = transaction_2.get_account(account_1.get_id())

        self.assertRaises(Spine.Errors.AlreadyLockedError, account_2.get_name)

        transaction_1.rollback()
        assert len(self.session.get_transactions()) == 1
        account_2.get_name()
        transaction_2.rollback()
        assert len(self.session.get_transactions()) == 0

    def testWriteLockWithWrite(self):
        """Comfirm that it's impossible to get a write lock on an already
        write-locked object."""
        transaction_1 = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 1
        transaction_2 = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 2

        account_1 = transaction_1.get_account_searcher().search()[0]
        account_1.set_name('Test')
        account_2 = transaction_2.get_account(account_1.get_id())

        self.assertRaises(Spine.Errors.AlreadyLockedError, account_2.set_name, 'Test')

        transaction_1.rollback()
        assert len(self.session.get_transactions()) == 1
        account_2.set_name('Test')
        transaction_2.rollback()
        assert len(self.session.get_transactions()) == 0

    def testMultipleReferences(self):
        """Confirm that the locks hold when fetching references to the same
        object several times."""
        transaction_1 = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 1

        account_1 = transaction_1.get_account_searcher().search()[0]
        account_2 = transaction_1.get_account(account_1.get_id()) # This read locks account_1

        assert account_2.get_id() == account_1.get_id() # The accounts should be the same

        account_1.set_name('Test') # Write lock
        account_2.set_name('Test2') # Should work just fine (already write locked by us)

        transaction_1.rollback()
        assert len(self.session.get_transactions()) == 0

        # Now do the same again with a different reference locking the account
        transaction_1 = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 1

        account_1 = transaction_1.get_account_searcher().search()[0]
        account_2 = transaction_1.get_account(account_1.get_id()) # This read locks account_1

        assert account_2.get_id() == account_1.get_id() # The accounts should be the same

        account_2.set_name('Test2') # Write lock
        account_1.set_name('Test') # Should work just fine (already write locked by us)

        transaction_1.rollback()
        assert len(self.session.get_transactions()) == 0

    def testDenyWritelockOnReadlockedObject(self):
        """Tests that a write lock is denied when an object is already read locked."""
        t1 = self.session.new_transaction()
        t2 = self.session.new_transaction()

        a1 = t1.get_account_searcher().search()[0]
        a1.get_name()

        a2 = t2.get_account_searcher().search()[0]
        self.assertRaises(Spine.Errors.AlreadyLockedError, a2.set_name, 'foo')
        t2.rollback()
        t1.rollback()



if __name__ == '__main__':
    unittest.main()
