#!/usr/bin/env python

import Gro
import Cerebrum_core.Errors as GroErrors
import config
import unittest
from doc_exception import *

class SyncError(DocstringException):
    "General Sync error"

class ServerError(SyncError):
    "Server error"

class LoginError(SyncError):
    "Could not login"

class Sync:
    def __init__(self):
        self._transactions = []
        self.connect()
   
    def __del__(self):
        # We shouldn't have any transactions now, but if we
        # do, we abort them.
        if self._transactions:
            print "WARNING: %s transactions still open" % len(self._transactions)
        self.rollback()
    
    def rollback(self):
        """Rolls back any open transactions"""
        for t in self._transactions:
            try:
                t.rollback()        
            except GroErrors.TransactionError:
                pass    
        self._transactions = []

    def connect(self):    
        try:
            self.gro = Gro.connect()
        except GroErrors.ServerError:
            raise ServerError    
        user = config.sync.get("gro", "login")
        password = config.sync.get("gro", "password")

        # Will have to use AP handler while LO handler
        # is redesigned 
        # self.lo = self.gro.get_lo_handler()
        try:
            self.ap = self.gro.get_ap_handler(user, password)
        except GroErrors.LoginError, e:
            raise LoginError, user
   
    def transaction(self):
        try:
            t = self.ap.new_transaction()         
        except GroErrors.ServerError:
            # let's naivly try to reconnect 
            self.connect()
            # This time it should work!    
            try:
                t = self.ap.new_transaction()         
            except GroErrors.ServerError:
                raise ServerError
        self._transactions.append(t)    
        return t    

    def get_accounts(self):
        t = self.transaction()
        search = t.get_account_search()
        accounts = search.search()
        results = []
        for account in accounts:
            a = Account()
            a.id = account.get_id()
            a.name = account.get_name()
            a.passwords = account.get_authentications()
            # Should select hash
            a.password = a.passwords[0] 
            try:
                a.gecos = account.get_gecos()
                a.uid = account.get_posix_uid()
                a.shell = account.get_shell()
            except Exception, e:
                print "Not posix", a.name
                a.gecos = ""
                a.uid = None
                a.shell = None
            results.append(a)
        t.rollback()
        return results

class Account:
    def __repr__(self):
        return "<Account %s %r>" % (self.name, self.gecos)
    
class TestConnect(unittest.TestCase):
    def testConnect(self):
        # Constructor connects
        sync = Sync()
        
    def testReConnect(self):
        sync = Sync()
        sync.connect()
    
class TestAPHandler(unittest.TestCase):
    def setUp(self):
        self.sync = Sync()    

    def testNewTransaction(self):
        t = self.sync.ap.new_transaction()
        t.rollback()
        t = self.sync.ap.new_transaction()
        t.commit()

    def testGetTransactions(self):
        t = self.sync.ap.new_transaction()
        transactions = self.sync.ap.get_transactions()
        equal = [t1 for t1 in transactions if t1._is_equivalent(t) ]
        self.assertEqual(len(equal), 1)
        t.rollback()

class TestTransaction(unittest.TestCase):
    # Test methods in transactions
    def setUp(self):
        self.sync = Sync()        
        self.t = self.sync.ap.new_transaction()
    
    def tearDown(self):
        self.t.rollback()    

    def testAccountSearch(self):
        search = self.t.get_account_search()
        result = search.search()
        assert result
            

class TestSync(unittest.TestCase):
    def setUp(self):
        self.s = Sync()
    
    def tearDown(self):
        del self.s    

    def testTransaction(self):
        t = self.s.transaction()
        assert t in self.s._transactions
        t.rollback()

    def testRollback(self):
        t = self.s.transaction()
        #self.s.rollback()
        #self.assertRaises(GroErrors.TransactionError, t.rollback)
            

if __name__ == "__main__":
    unittest.main()

# arch-tag: 2be20b9a-fdb1-4975-bd42-8afec3238306
