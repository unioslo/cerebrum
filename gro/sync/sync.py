#!/usr/bin/env python

import Gro
import Cerebrum_core.Errors as GroErrors
import config
import unittest
import sys
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
        self._connect()
   
    def __del__(self):
        # We shouldn't have any open transactions now, but if we do, we
        # abort them.
        if self._open_transactions():
            print >>sys.stderr, "WARNING: %s transactions still open" % len(self._transactions)
        self._rollback()
    
    def _rollback(self):
        """Rolls back any open transactions"""
        for t in self._transactions:
            try:
                t.rollback()        
            except GroErrors.TransactionError:
                pass    
        self._transactions = []

    def _open_transactions(self):
        """Returns current open transactions opened by self. 
           Removes closed transactions from self._transactions.
        """
        my_transactions = self._transactions
        open_transactions = self.ap.get_transactions()
        self._transactions = [my for my in my_transactions 
                  if filter(my._is_equivalent, open_transactions)]
        return self._transactions              

    def _connect(self):    
        """Connect and login to Gro"""
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
   
    def _transaction(self):
        """Get a transaction from Gro. Note that you must
           commit or rollback the transaction when finished."""
        try:
            t = self.ap.new_transaction()         
        except GroErrors.ServerError:
            # let's naivly try to reconnect 
            self._connect()
            # This time it should work!    
            try:
                t = self.ap.new_transaction()         
            except GroErrors.ServerError:
                raise ServerError
        self._transactions.append(t)    
        return t    

    def get_accounts(self):
        """Get all accounts from Gro. Returns a list of Account objects."""
        t = self._transaction()
        search = t.get_account_search()
        accounts = search.search()
        results = []
        for account in accounts:
            a = Account(account)
            results.append(a)
        t.rollback()
        return results

    def get_groups(self):
        t = self._transaction()
        search = t.get_group_search()
        groups = search.search()
        results = []
        for group in groups:
            g = Group(group)
            results.append(g)
        t.rollback()
        return results
 
class Group:           
    """Stub object for representation of an account"""
    def __init__(self, group):
        # Internal Cerebrum ID 
        self.id = group.get_id()
        # Username
        self.name = group.get_name()
        # Description
        self.description = group.get_description()
        # Complete list of members (usernames) 
        members = group.get_members()
        # Account objects 
        self.members = [ Account(a) for a in members ]
        # Just the usernames
        self.membernames = [ a.name for a in self.members ]
        try:
            # Posix 
            self.gid = group.get_posix_gid()
            dir(group)
        except Exception, e:
            self.gid = None    

    def __repr__(self):
        return "<Group %s>" % self.name

class Account:
    """Stub object for representation of an account"""
    def __init__(self, account):
        # Internal Cerebrum ID 
        self.id = account.get_id()
        # Username
        self.name = account.get_name()
        auths = account.get_authentications()
        # Dictionary of password hashes, hashmethod as key
        self.passwords = dict([ (auth.get_method().get_name(), auth.get_auth_data() )
                            for auth in auths ])
        # OBSOLETE: Preferred password hash
        self.password = self.passwords['MD5-crypt'] 
        # Should get home directory from server.. must be
        # related to the active spread or something like that.
        self.home = "/home/%s" % self.name
        try:
            # POSIX-enabled features 
            # Full name
            self.fullname = account.get_gecos()
        except Exception, e:
            #print "Not posix", self.name
            # owner = account.get_owner() 
            # Should do owner.get_names() or something.. but that
            # doesn't work. We'll just write the username as the
            # fullname instead
            # Since we don't have POSIX, set to None
            self.fullname = self.name
            self.gid = None
            self.uid = None
            self.shell = None
        else:    
            # Rest of POSIX stuff 
            # get_gid returns a Group instance, not a gid =)
            group = account.get_gid() 
            self.gid = group.get_posix_gid()
            self.uid = account.get_posix_uid()
            self.shell = account.get_shell().get_shell()

    def __repr__(self):
        return "<Account %s %r>" % (self.name, self.fullname)
    
class TestConnect(unittest.TestCase):
    def testConnect(self):
        # Constructor connects
        sync = Sync()
        
    def testReConnect(self):
        sync = Sync()
        sync._connect()
    
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
        assert len(result) > 0
            

class TestSync(unittest.TestCase):
    def setUp(self):
        self.s = Sync()
    
    def tearDown(self):
        del self.s    

    def testTransaction(self):
        t = self.s._transaction()
        assert t in self.s._transactions
        assert t in self.s._open_transactions()
        t.rollback()
        # open_transactions() should remove it 
        assert t not in self.s._open_transactions()
        assert t not in self.s._transactions

    def testRollback(self):
        t = self.s._transaction()
        self.s._rollback()
        # If the t is rolled back, we shouldn't be able to roll back
        # again 
        self.assertRaises(GroErrors.TransactionError, t.rollback)
    
    def testGetAccounts(self):
        accounts = self.s.get_accounts()
        assert accounts
        # We can assume that bootstrap_account exists for now 
        has_bootstrap = filter(lambda a: a.name == 'bootstrap_account', accounts)
        assert has_bootstrap
        bootstrap = has_bootstrap[0]
        assert bootstrap.fullname == "bootstrap_account"
        assert bootstrap.password
        # And he doesn't have any of those POSIX stuff 
        assert not bootstrap.uid 
        assert not bootstrap.gid
        assert not bootstrap.shell
            

if __name__ == "__main__":
    unittest.main()

# arch-tag: 2be20b9a-fdb1-4975-bd42-8afec3238306
