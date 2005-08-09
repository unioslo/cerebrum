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

class TransactionTest(unittest.TestCase):
    def setUp(self):
        self.session = spine.login(username, password)

    def tearDown(self):
        self.session.logout()

    def testRollback(self):
        """Open a transaction and rollback immediately."""
        transaction = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 1
        transaction.rollback()
        assert len(self.session.get_transactions()) == 0

    def testCommit(self):
        """Open a transaction and commit immediately."""
        transaction = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 1
        transaction.commit()
        assert len(self.session.get_transactions()) == 0

    def testMultipleCommit(self):
        """Open two transaction and commit both immediately."""
        t1 = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 1
        t2 = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 2
        t1.commit()
        assert len(self.session.get_transactions()) == 1
        t1 = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 2
        t2.commit()
        assert len(self.session.get_transactions()) == 1
        t1.commit()
        assert len(self.session.get_transactions()) == 0

    def testMultipleRollback(self):
        """Open two transaction and rollback both immediately."""
        t1 = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 1
        t2 = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 2
        t1.rollback()
        assert len(self.session.get_transactions()) == 1
        t1 = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 2
        t2.rollback()
        assert len(self.session.get_transactions()) == 1
        t1.rollback()
        assert len(self.session.get_transactions()) == 0

    def testRollbackWithoutChange(self):
        """Start a transaction, fetch a search object and rollback the
        transaction."""
        transaction = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 1
        transaction.get_disk_searcher()
        transaction.rollback()
        assert len(self.session.get_transactions()) == 0

    def testCommitWithoutChange(self):
        """Start a transaction, fetch a search object and commit."""
        transaction = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 1
        transaction.get_disk_searcher()
        transaction.commit()
        assert len(self.session.get_transactions()) == 0

    def testCommitWithChange(self):
        """Test that changes can be commited by setting a person name, commiting, setting the old name and commiting again."""
        transaction = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 1
        ous = transaction.get_ou_searcher().search()
        assert len(ous) >= 1 # We need an OU to continue the test
        ou = ous[0]
        ou_id = ou.get_id()
        old_name = ou.get_name()
        ou.set_name(str(id(ou)))
        transaction.commit()
        assert len(self.session.get_transactions()) == 0

        transaction = self.session.new_transaction()
        ou = transaction.get_ou(ou_id)
        ou.set_name(old_name)
        transaction.commit()
        assert len(self.session.get_transactions()) == 0

    def testTransactionsAndVerifyData(self):
        """Test that a change can be commited and verifies that the change is
        stored."""
        transaction = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 1
        account = transaction.get_account_searcher().search()[0]
        new_name = str(id(account))
        id_1 = account.get_id()
        name = account.get_name()
        account.set_name(new_name)
        transaction.commit()
        assert len(self.session.get_transactions()) == 0

        transaction = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 1
        account = transaction.get_account(id_1)
        self.assertEquals(account.get_name(), new_name)
        account.set_name(name)
        transaction.commit()
        assert len(self.session.get_transactions()) == 0

        transaction = self.session.new_transaction()
        account = transaction.get_account(id_1)
        self.assertEquals(account.get_name(), name)
        transaction.rollback()
        assert len(self.session.get_transactions()) == 0

class MultipleTransactionTest(unittest.TestCase):
    def setUp(self):
        self.session = spine.login(username, password)

    def tearDown(self):
        self.session.logout()

    def testMultipleTransactionsWithDifferentObjects(self):
        """Test multiple transaction manipulating different objects, commiting changes and verifying that they were written to the database."""
        transaction_1 = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 1
        transaction_2 = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 2
        search = transaction_1.get_account_searcher().search()
        assert len(search) >= 2 # We need two accounts to continue the test
        account_1 = search[0]
        test_name = str(id(account_1))
        test_name2 = str(id(account_1) + 1)
        account_2 = search[1]
        id_1 = account_1.get_id()
        id_2 = account_2.get_id()
        name_1 = account_1.get_name()
        name_2 = account_2.get_name()
        account_1.set_name(test_name)
        account_2.set_name(test_name2)
        transaction_1.commit()
        assert len(self.session.get_transactions()) == 1
        transaction_2.commit()
        assert len(self.session.get_transactions()) == 0

        transaction_1 = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 1
        transaction_2 = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 2
        account_1 = transaction_1.get_account(id_1)
        account_2 = transaction_1.get_account(id_2)
        self.assertEquals(account_1.get_name(), test_name)
        self.assertEquals(account_2.get_name(), test_name2)
        account_1.set_name(name_1)
        account_2.set_name(name_2)
        transaction_1.commit()
        assert len(self.session.get_transactions()) == 1
        transaction_2.commit()
        assert len(self.session.get_transactions()) == 0

        transaction_1 = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 1
        transaction_2 = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 2
        account_1 = transaction_1.get_account(id_1)
        account_2 = transaction_2.get_account(id_2)
        self.assertEquals(account_1.get_name(), name_1)
        self.assertEquals(account_2.get_name(), name_2)
        transaction_1.rollback()
        assert len(self.session.get_transactions()) == 1
        transaction_2.rollback()
        assert len(self.session.get_transactions()) == 0

    # TODO: Rewrite test to suite the database transactions
    def skipMultipleTransactionsWithSameObjects(self):
        """Test multiple transactions operating on the same object (verifies that locking works as expected)."""
        transaction_1 = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 1
        transaction_2 = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 2
        account_1 = transaction_1.get_account_searcher().search()[0]
        test_name = str(id(account_1))
        test_name2 = str(id(account_1) + 1)
        id_1 = account_1.get_id()
        account_2 = transaction_2.get_account(id_1)
        name_1 = account_1.get_name()
        name_2 = account_2.get_name()
        self.assertEquals(name_1, name_2)
        transaction_2.commit()
        assert len(self.session.get_transactions()) == 1

        account_1.set_name(test_name)
        transaction_2 = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 2
        account_2 = transaction_2.get_account(id_1)

        #self.assertRaises(Spine.Errors.AlreadyLockedError, account_2.get_name)
        
        transaction_1.commit()
        assert len(self.session.get_transactions()) == 1
        transaction_1 = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 2
        account_1 = transaction_1.get_account(id_1)

        account_2.set_name(test_name2)

        #self.assertRaises(Spine.Errors.AlreadyLockedError, account_1.get_name)

        self.assertEquals(account_2.get_name(), test_name2)
        transaction_2.commit()
        assert len(self.session.get_transactions()) == 1

        self.assertEquals(account_1.get_name(), test_name2)
        account_1.set_name(name_1)
        transaction_1.commit()
        assert len(self.session.get_transactions()) == 0

        transaction_1 = self.session.new_transaction()
        assert len(self.session.get_transactions()) == 1
        account_1 = transaction_1.get_account(id_1)
        self.assertEquals(account_1.get_name(), name_1)
        transaction_1.rollback()
        assert len(self.session.get_transactions()) == 0

if __name__ == '__main__':
    unittest.main()
