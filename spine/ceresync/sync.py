#!/usr/bin/env python
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

import Spine
import SpineIDL.Errors as SpineErrors
import config
import unittest
import sys
import sets
import errors

def fixOmniORB():
    """Workaround for bugs in omniorb

    Makes it possible to use obj1 == obj2 instead of having to do
    obj1._is_equivalent(obj2).
    Also makes it possible to use corba objects as keys in
    dictionaries etc.
    """
    import omniORB.CORBA
    import _omnipy
    def __eq__(self, other):
        if self is other:
            return True
        return _omnipy.isEquivalent(self, other)

    def __hash__(self):
        # sys.maxint is the maximum value returned by _hash
        return self._hash(sys.maxint)

    omniORB.CORBA.Object.__hash__ = __hash__
    omniORB.CORBA.Object.__eq__ = __eq__

try:
    import omniORB
    fixOmniORB()
except:
    pass

class Sync:
    def __init__(self, incr=False, id=None):
        """Creates a sync connection to Spine. 

        If incr is true, the parameter id must be supplied, and only
        changed object since that change id will be returned from
        get_-methods

        If incr is false, all objects will be returned

        The last change_id for the supplied objects 
        is supplied in the attribute last_change, both for incr=True
        and incr=False.
        """

        self._transactions = []
        self.connection = None
        self._connect()
   
        if incr:
            if id is None:
                raise errors.ProgrammingError, "Must supply 'id' argument"
            self._connection = self._transaction()
        else:
            # Snapshots are not rolled back when rollback is called :( 
            #self._connection = self._snapshot()
            self._connection = self._transaction()

        self._from_change = id
        self.last_change = self._connection.get_commands().get_last_changelog_id()

        if incr:
            self._changes = self._connection.get_change_log_searcher()
            self._changes.set_id_more_than(self._from_change)
            self._changes.set_id_less_than(self.last_change + 1)
            self._changes.mark_subject()
#            print 'changes:', self._changes.search()
#            print 'getting changes from %s to %s' % (self._from_change, self.last_change)
        else:
            self._changes = None
#            print 'getting everything'

    """
    def __del__(self):
        # We roll back our own passive main connection
        if self._connection:
            self._connection.rollback()
        # We shouldn't have any open transactions now, but if we do, we
        # abort those too. Such connections could have been created by
        # modules who need to make other _transaction()s.
        if self._open_transactions():
            print >>sys.stderr, "WARNING: %s transactions still open, rolling back" % len(self._transactions)
        self._rollback()
"""
    
    def _rollback(self):
        """Rolls back any open transactions"""
        for t in self._transactions:
            try:
                t.rollback()        
            except SpineErrors.TransactionError:
                pass
        self._transactions = []
        self._connection = None

    def _open_transactions(self):
        """Returns current open transactions opened by self. 
           Removes closed transactions from self._transactions.
        """
        my_transactions = self._transactions
        open_transactions = self._handler.get_transactions()
        self._transactions = [my for my in my_transactions 
                  if filter(my._is_equivalent, open_transactions)]
        return self._transactions              

    def _connect(self):    
        """Connect and login to Spine"""
        try:
            self.spine = Spine.connect()
        except SpineErrors.ServerError:
            raise errors.ServerError, "Could not connect to Spine"    
        user = config.sync.get("spine", "login")
        password = config.sync.get("spine", "password")

        try:
            self._handler = self.spine.login(user, password)
        except SpineErrors.LoginError, e:
            raise errors.LoginError, "Spine user %s" % user
   
    def _transaction(self):
        """Get a transaction from Spine. Note that you must
           commit or rollback the transaction when finished."""
        try:
            t = self._handler.new_transaction()         
        except SpineErrors.ServerError:
            # let's naivly try to reconnect 
            self._connect()
            # This time it should work!    
            try:
                t = self._handler.new_transaction()         
            except SpineErrors.ServerError:
                raise errors.ServerError, "Could not create new Spine transaction"
        self._transactions.append(t)    
        return t    

    def _snapshot(self):
        """Get a snapshot from Spine."""
        try:
            t = self._handler.snapshot()         
        except SpineErrors.ServerError:
            # let's naivly try to reconnect 
            self._connect()
            # This time it should work!    
            try:
                t = self._handler.snapshot()         
            except SpineErrors.ServerError:
                raise errors.ServerError, "Could not create new Spine snapshot"
        self._transactions.append(t)    
        return t    

    def close(self):
        self._rollback()

    def get_accounts(self):
        """Get all accounts from Spine. Returns a list of Account objects."""
        t = self._connection

        # create a search
        account_search = t.get_account_searcher()
        if self._changes:
            account_search.set_intersections([self._changes])

        # create a dumper and mark what we want to dump
        dumper = account_search.get_dumper()
        dumper.mark_name()
        dumper.mark_posix_uid()
        dumper.mark_primary_group()         # reference
        dumper.mark_shell()                 # reference
        dumper.mark_gecos()
        dumper.mark_get_authentications()   # references

        # dump all accounts
        accounts = dumper.dump()

        # map all groups
        group_dumper = dumper.dump_primary_group()
        group_dumper.mark_posix_gid()
        groups = {}
        for i in group_dumper.dump():
            groups[i.reference] = i

        # map all shells
        shell_dumper = dumper.dump_shell()
        shell_dumper.mark_name()
        shell_dumper.mark_shell()
        shells = {}
        for i in shell_dumper.dump():
            shells[i.reference] = i

        # map all authentications
        auths = []
        for i in accounts:
            auths += i.get_authentications
        auth_dumper = t.get_account_authentication_dumper(auths)
        auth_dumper.mark_auth_data()
        auth_dumper.mark_method()
        auths = {}
        for i in auth_dumper.dump():
            auths[i.reference] = i

        # replace corba references with the mappings we have made
        for i in accounts:
            i.get_authentications = [auths[j] for j in i.get_authentications]

            # make a nice mapping between method:data
            i.passwords = {}
            types = {}
            for auth in i.get_authentications:
                if auth.method not in types:
                    types[auth.method] = auth.method.get_name()
                i.passwords[types[auth.method]] = auth.auth_data

            # Should get home directory from server.. must be
            # related to the active spread or something like that.
            i.home = "/home/%s" % i.name

            if i.posix_uid_exists:
                i.primary_group = groups[i.primary_group]
                i.shell = shells[i.shell].shell
            else:
                i.posix_uid = None
                i.gecos = None
                i.primary_group = None
                i.shell = None

            i.type = 'account'
        return accounts

    def get_groups(self):
        t = self._connection

        # create a search
        group_search = t.get_group_searcher()
        if self._changes:
            group_search.set_intersections([self._changes])

        # create a dumper and mark what we want to dump
        dumper = group_search.get_dumper()
        dumper.mark_name()
        dumper.mark_get_members()   # references
        dumper.mark_posix_gid()

        # dump all accounts
        groups = dumper.dump()

        # map all accounts
        members = sets.Set()
        for i in groups:
            members.union_update(i.get_members)
        account_dumper = t.get_account_dumper(list(members))
        account_dumper.mark_name()

        accounts = {}
        for i in account_dumper.dump():
            accounts[i.reference] = i

        for group in groups:
            group.get_members = [accounts[i] for i in group.get_members]
            group.membernames = [i.name for i in group.get_members]
            if not group.posix_gid_exists:
                group.posix_gid = None

            group.type = 'group'

        return groups

    def get_persons(self):
        t = self._connection
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
        return results

    def get_changes(self):
        """
        returns a list with (type, operation, object) tuples

        type can be ACCOUNT, GROUP, PERSON, OU
        operation can be ADD, UPDATE, DELETE

        when doing DELETE operations, object is the primary key (i.e username) 
        """

        s = self._changes.get_dumper()

        # get all types
        ts = s.dump_type()
        ts.mark_category()
        ts.mark_type()
        ts.mark_msg()
        types = {}
        for i in ts.dump():
            types[i.reference] = i

        s.mark_type()
        s.mark_subject()
        s.mark_subject_entity()
        changes = []
        for i in s.dump():
            changes.append((i.id, types[i.type], i))

        changes.sort() # make sure changes are in correct order

        changed = set()

        entities = {}
        for i in self.get_accounts():
            entities[i.id] = i
        for i in self.get_groups():
            entities[i.id] = i

        for id, change, log in changes:
            if change.category == 'entity' and change.type == 'del':
                yield 'del', log.subject_entity
                continue

            # Skip repeated changes or entities we dont care about
            if log.subject_entity not in entities:
                continue

            if change.category == 'entity' and change.type == 'add':
                yield 'add', entities[log.subject_entity]

            else: # everything else is updates
                yield 'update', entities[log.subject_entity]

            del entities[log.subject_entity]

        assert not entities # all entities must have been processed

    def get_all(self):
        for i in self.get_accounts():
            yield 'add', i
        for i in self.get_groups():
            yield 'add', i

    def get_objects(self):
        if self._changes is None:
            return self.get_all()
        else:
            return self.get_changes()

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

        self.deceased = person.get_deceased()

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
        t = self.sync._handler.new_transaction()
        t.rollback()
        t = self.sync._handler.new_transaction()
        t.commit()

    def testGetTransactions(self):
        t = self.sync._handler.new_transaction()
        transactions = self.sync._handler.get_transactions()
        equal = [t1 for t1 in transactions if t1._is_equivalent(t) ]
        self.assertEqual(len(equal), 1)
        t.rollback()

class TestTransaction(unittest.TestCase):
    # Test methods in transactions
    def setUp(self):
        self.sync = Sync()        
        self.t = self.sync._handler.new_transaction()
    
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
        assert bootstrap.name == "bootstrap_account"
        assert bootstrap.passwords
        # And he doesn't have any of those POSIX stuff 
        assert not bootstrap.posix_uid 
        assert not bootstrap.primary_group
        assert not bootstrap.shell

        # Test for a known POSIX account
        # FIXME: Should have a predefined (or inserted)
        # Posix account instead of relying on stain being present
        stains = [a for a in accounts if a.name == "stain"]
        assert stains
        stain = stains[0]
        assert stain.posix_uid > 0
        # Should not be group name, group object, etc.. just gid 
        assert type(stain.primary_group.posix_gid) == int
        assert stain.primary_group.posix_gid > 0
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
        assert not bootstrap.posix_gid
        # Only member should be bootstrap_account 
        members = bootstrap.get_members 
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
