#!/usr/bin/env python

import Spine
import Cerebrum_core.Errors as SpineErrors
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
            print >>sys.stderr, "WARNING: %s transactions still open, rolling back" % len(self._transactions)
        self._rollback()
    
    def _rollback(self):
        """Rolls back any open transactions"""
        for t in self._transactions:
            try:
                t.rollback()        
            except SpineErrors.TransactionError:
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
        """Connect and login to Spine"""
        try:
            self.spine = Spine.connect()
        except SpineErrors.ServerError:
            raise ServerError    
        user = config.sync.get("spine", "login")
        password = config.sync.get("spine", "password")

        # Will have to use AP handler while LO handler
        # is redesigned 
        # self.lo = self.spine.get_lo_handler()
        try:
            self.ap = self.spine.login(user, password)
        except SpineErrors.LoginError, e:
            raise LoginError, user
   
    def _transaction(self):
        """Get a transaction from Spine. Note that you must
           commit or rollback the transaction when finished."""
        try:
            t = self.ap.new_transaction()         
        except SpineErrors.ServerError:
            # let's naivly try to reconnect 
            self._connect()
            # This time it should work!    
            try:
                t = self.ap.new_transaction()         
            except SpineErrors.ServerError:
                raise ServerError
        self._transactions.append(t)    
        return t    

    def get_accounts(self):
        """Get all accounts from Spine. Returns a list of Account objects."""
        t = self._transaction()
        search = t.get_account_searcher()
        #dumper = search.get_dumper()
        #dumper.mark_whatever()
        #accounts = dumper.dump()
        # since dumper does not work yet, we'll do it the old way 
        accounts = search.search()
        results = []
        for account in accounts:
            a = Account(account)
            results.append(a)
        t.rollback()
        return results

    def get_groups(self):
        t = self._transaction()
        search = t.get_group_searcher()
        groups = search.search()
        results = []
        for group in groups:
            g = Group(group)
            results.append(g)
        t.rollback()
        return results

    def get_persons(self):
        t = self._transaction()
        search = t.get_person_searcher()
        persons = search.search()
        results = []
        for p in persons:
            person = Person(p)
            results.append(person)

            # Find user names for person
            # (this might get heavy: FIXME) 
            accounts = t.get_account_searcher()
            accounts.set_owner(p)
            # FIXME
            # WHICH IS THE PRIMARY USER? What about different user name
            # domains? 
            person.users = [a.get_name() for a in accounts.search()]

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
            group = account.get_primary_group() 
            self.gid = group.get_posix_gid()
            self.uid = account.get_posix_uid()
            self.shell = account.get_shell().get_shell()

    def __repr__(self):
        return "<Account %s %r>" % (self.name, self.fullname)

class Person:
    """Stub object for representation of a person"""
    def __init__(self, person):
        # Internal Cerebrum ID 
        self.id = person.get_id()

        # .name is always the "readable primary key"
        # as the backends should expect, and it happens to
        # to be that export_id is designed for just this purpose.
        # See self.full_name for full name of person. 
        self.name = person.get_export_id()

        self.type = person.get_type().get_name()
        self.description = person.get_description()
        # FIXME: Might get_b_date() and get_gender() return None or fail?
        self.birth_date = person.get_birth_date().strftime("%Y-%m-%d")
        # a letter like "F", "M", "X"  (female, male, unknown)
        self.gender = person.get_gender().get_name()
        # FIXME: untested as no person yet has any group
        self.groups = [g.get_name() for g in person.get_groups()]
        # FIXME: What about organizational belongings?

        # Map to true Python booleans
        bools = {"F": False, "T": True}
        self.deceased = bools[person.get_deceased()]

        # Unwrap PersonName objects
        names = person.get_names() 
        self.names = {}
        for name in names:
            variant = name.get_name_variant().get_name()
            name = name.get_name()
            self.names[variant] = name
            # Could also get source system of name variant, but why?
        self.full_name = self.names.get("FULL") # Could be None (when?)    
        
        # FIXME:  add: addresses, contact_info 
   
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
        search = self.t.get_account_searcher()
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
        self.assertRaises(SpineErrors.TransactionError, t.rollback)
    
    def testGetAccounts(self):
        accounts = self.s.get_accounts()
        assert accounts
        # We can assume that bootstrap_account exists for now 
        has_bootstrap = [a for a in accounts if a.name == 'bootstrap_account']
        assert has_bootstrap
        bootstrap = has_bootstrap[0]
        assert bootstrap.fullname == "bootstrap_account"
        assert bootstrap.password
        # And he doesn't have any of those POSIX stuff 
        assert not bootstrap.uid 
        assert not bootstrap.gid
        assert not bootstrap.shell

        # Test for a known POSIX account
        # FIXME: Should have a predefined (or inserted)
        # Posix account instead of relying on stain being present
        stains = [a for a in accounts if a.name == "stain"]
        assert stains
        stain = stains[0]
        assert stain.uid > 0
        # Should not be group name, group object, etc.. just gid 
        assert type(stain.gid) == int
        assert stain.gid > 0
        # HEHEHE 
        self.assertEqual(stain.shell, "/local/gnu/bin/bash")


    def testGetGroups(self):
        groups = self.s.get_groups()
        assert groups
        # We can assume that bootstrap_group exists for now 
        has_bootstrap = [g for g in groups if g.name == 'bootstrap_group']
        assert has_bootstrap
        bootstrap = has_bootstrap[0]
        assert "bootstrap_account" in bootstrap.membernames
        # Not a POSIX group
        assert not bootstrap.gid
        # Only member should be bootstrap_account 
        members = bootstrap.members 
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0].name, "bootstrap_account")
        # FIXME: Should test a posix group 
   
    def testGetPersons(self):
        persons = self.s.get_persons()
        assert persons
        soilands = [p for p in persons if p.full_name=="Stian Soiland"]
        assert soilands   # There's no other default person we can rely on..
        soiland = soilands[0]
        self.assertEqual(soiland.type, "person")
        # Can we trust the export ID to be on this format?
        self.assertEqual(soiland.name, "exp-%s" % soiland.id)
        # FIXME: Could contain more names
        self.assertEqual(soiland.names, { 'FULL': "Stian Soiland" })
        # FIXME: Should be 1979-02-15   =) 
        self.assertEqual(soiland.birth_date, "1971-02-01")
        # FIXME: Should be "M"  =)
        self.assertEqual(soiland.gender, "X")
        # at least for now.. 
        self.assertEqual(soiland.deceased, False)
        # FIXME: Should be "stain" and "soiland" in soiland.users
        self.assertEqual(soiland.users, ["cxx"])


if __name__ == "__main__":
    unittest.main()

# arch-tag: 2be20b9a-fdb1-4975-bd42-8afec3238306
