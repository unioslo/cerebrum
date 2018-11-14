#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Basic tests for Cerebrum/Account.py.

Searching (members and groups) has to be thoroughly tested.
"""
from __future__ import unicode_literals

import unittest

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.Account import Account
from datasource import BasicAccountSource, BasicPersonSource
from dbtools import DatabaseTools
from datasource import expired_filter, nonexpired_filter

# TODO:
#
# Not imploemented tests for
#  - Account/AccountType
#  - Account/AccountHome


# Simple lamda-function to create a set of account_ids/entity_ids from a
# sequence of dicts (or dict-like objects).
# Lookup order is 'entity_id' -> 'account_id'. If none of the keys exist or
# if a key exist but doesn't have an intval, a ValueError is raised.
_set_of_ids = lambda accs: \
    set((int(a.get('entity_id', a.get('account_id'))) for a in accs))


class BaseAccountTest(unittest.TestCase):
    """
    This is a testcase for Cerebrum.Account class.

    No subclass or mixin should cause this test to fail, so the test is valid
    for other setups as well.
    Mixins and subclasses can subclass this test in order to perform additional
    setup and tests.
    """

    @classmethod
    def setUpClass(cls):
        """
        Set up this TestCase module.

        This setup code sets up shared objects between each tests. This is done
        *once* before running any of the tests within this class.
        """

        # TODO: We might want this basic class setup in other TestCases. Maybe
        #       set up a generic TestCase class to inherit common stuff from?
        cls._db = Factory.get('Database')()
        cls._db.cl_init(change_program='nosetests')
        cls._db.commit = cls._db.rollback  # Let's try not to screw up the db

        cls._ac = Factory.get('Account')(cls._db)
        cls._ac = Account(cls._db)
        cls._co = Factory.get('Constants')(cls._db)

        # Data sources
        cls.account_ds = BasicAccountSource()
        cls.person_ds = BasicPersonSource()

        # Tools for creating and destroying temporary db items
        cls.db_tools = DatabaseTools(cls._db)
        cls.db_tools._ac = cls._ac

    @classmethod
    def tearDownClass(cls):
        """ Clean up this TestCase class. """
        cls.db_tools.clear_groups()
        cls.db_tools.clear_accounts()
        cls.db_tools.clear_persons()
        cls.db_tools.clear_constants()
        cls._db.rollback()


class SimpleAccountsTest(BaseAccountTest):
    """ This is a test case for simple scenarios. """

    def test_account_populate(self):
        """ Account.populate() with basic info. """
        creator_id = self.db_tools.get_initial_account_id()
        owner_id = self.db_tools.get_initial_group_id()
        account = self.account_ds.get_next_item()

        self._ac.clear()
        self._ac.populate(account['account_name'], self._co.entity_group,
                          owner_id, self._co.account_program, creator_id, None)
        self._ac.write_db()
        self.assertTrue(hasattr(self._ac, 'entity_id'))

        entity_id = self._ac.entity_id
        self._ac.clear()
        self._ac.find(entity_id)
        self.assertEqual(self._ac.account_name, account['account_name'])

        # If the test fails, there's nothing to clean up.
        # If it succeeds, we can delete the account
        self.db_tools.delete_account_id(entity_id)

    def test_account_create(self):
        """ Account.create() with a new person. """
        creator_id = self.db_tools.get_initial_account_id()
        owner_id = self.db_tools.create_person(self.person_ds.get_next_item())
        self.addCleanup(self.db_tools.delete_person_id, owner_id)

        account = self.account_ds.get_next_item()
        self._ac.clear()
        self._ac.populate(account['account_name'], self._co.entity_person,
                          owner_id, None, creator_id, None)
        self._ac.write_db()
        self.assertTrue(hasattr(self._ac, 'entity_id'))

        entity_id = self._ac.entity_id
        self._ac.clear()
        self._ac.find(entity_id)

        self.assertEqual(self._ac.account_name, account['account_name'])
        self.db_tools.delete_account_id(entity_id)


class MultipleAccountsTest(BaseAccountTest):
    """ This is a testcase where multiple accounts exists in the system.

    Tests of search functions, list functions, and other tests that depend on
    existing accounts should go here. Before every test, a set of accounts are
    created, and those accounts are cleared after each test.
    """

    def setUp(self):
        """ Prepare test.

        Sets up a series of accounts for testing, and queues a cleanup function
        to remove those accounts.
        """
        self._accounts = []
        for account in self.account_ds(limit=5):
            entity_id = self.db_tools.create_account(account)
            account['entity_id'] = entity_id
            self._accounts.append(account)
            self.addCleanup(self.db_tools.delete_account_id, entity_id)

    # Tests start here

    def test_simple_find(self):
        """ Account.find() accounts. """
        # Fails if we get a Cerebrum.NotFoundException
        assert len(self._accounts) >= 1  # We need at least 1 account
        count = 0
        for account in self._accounts:
            self._ac.clear()
            self._ac.find(account['entity_id'])
            count += 1
        self.assertEqual(len(self._accounts), count)

    def test_simple_find_fail(self):
        """ Account.find() non-existing account. """
        self._ac.clear()

        # negative IDs are impossible in Cerebrum, should raise notfound-error
        self.assertRaises(Errors.NotFoundError, self._ac.find, -10)

    def test_find_by_name(self):
        """ Account.find_by_name() accounts. """
        assert len(self._accounts) >= 1  # We need at least 1 account
        count = 0
        for account in self._accounts:
            self._ac.clear()
            self._ac.find_by_name(account['account_name'])
            count += 1
        self.assertEqual(len(self._accounts), count)

    def test_find_by_name_fail(self):
        """ Account.find_by_name() non-existing account. """
        self._ac.clear()

        # entity_name is a varchar(256), no group with longer name should exist
        self.assertRaises(Errors.NotFoundError, self._ac.find_by_name,
                          'n' * (256+1))

    def test_is_expired(self):
        """ Account.is_expired() for expired and non-expired accounts. """
        non_expired = _set_of_ids(filter(nonexpired_filter, self._accounts))

        # We must have at least one expired and one non-expired account
        assert (len(non_expired) > 0 and
                len(non_expired) < len(_set_of_ids(self._accounts)))

        for account in self._accounts:
            self._ac.clear()
            self._ac.find(account['entity_id'])
            if int(self._ac.entity_id) in non_expired:
                self.assertFalse(self._ac.is_expired())
            else:
                self.assertTrue(self._ac.is_expired())

    def test_search_owner(self):
        """ Account.search() with owner_id argument. """
        created_ids = _set_of_ids(self._accounts)
        owner_id = self.db_tools.get_initial_group_id()
        self.assertGreaterEqual(len(created_ids), 1)

        results = self._ac.search(owner_id=owner_id, expire_start=None)
        owned_by = _set_of_ids(results)

        # INITIAL_GROUPNAME could own more than what we've created, but all our
        # created groups should be returned by the search
        self.assertGreaterEqual(len(owned_by), len(created_ids))
        self.assertTrue(owned_by.issuperset(created_ids))

        # We should not get any results with another owner_id
        for result in results:
            self.assertEqual(int(result['owner_id']),
                             self.db_tools.get_initial_group_id())

    def test_search_owner_sequence(self):
        """ Account.search() with sequence owner_id argument. """
        created_ids = _set_of_ids(self._accounts)
        self.assertGreaterEqual(len(created_ids), 1)

        # Creator of our default accounts
        group_id = self.db_tools.get_initial_group_id()

        # Create a person, so that we can create a personal acocunt
        person_id = self.db_tools.create_person(
            self.person_ds.get_next_item())
        self.addCleanup(self.db_tools.delete_person_id, person_id)

        # Create a personal account, and add to our created_ids
        account = self.account_ds.get_next_item()
        account_id = self.db_tools.create_account(
            account, person_owner_id=person_id)
        self.addCleanup(self.db_tools.delete_account_id, account_id)

        created_ids.add(account_id)

        for seq_type in (set, list, tuple):
            sequence = seq_type((person_id, group_id))
            results = list(self._ac.search(owner_id=sequence,
                                           expire_start=None))
            owned_by_seq = _set_of_ids(results)
            self.assertGreaterEqual(len(results), len(created_ids) + 1)
            self.assertTrue(owned_by_seq.issuperset(created_ids))
            for result in results:
                self.assertIn(int(result['owner_id']), sequence)

    def test_search_filter_expired(self):
        """ Account.search() with expire_start, expire_stop args. """
        all = _set_of_ids(self._accounts)
        non_expired = _set_of_ids(filter(nonexpired_filter, self._accounts))
        expired = _set_of_ids(filter(expired_filter, self._accounts))

        # Test criterias
        self.assertGreaterEqual(len(non_expired), 1)
        self.assertGreaterEqual(len(expired), 1)

        # Tests: search params, must match
        for params, match_set, fail_set in (
                ({'expire_start': None, 'expire_stop': None,
                  'owner_id': self.db_tools.get_initial_group_id()},
                 all, set()),
                ({'expire_start': '[:now]', 'expire_stop': None,
                  'owner_id': self.db_tools.get_initial_group_id()},
                 non_expired, expired),
                ({'expire_start': None, 'expire_stop': '[:now]',
                  'owner_id': self.db_tools.get_initial_group_id()},
                 expired, non_expired),):
            result = _set_of_ids(self._ac.search(**params))
            self.assertGreaterEqual(len(result), len(match_set))
            self.assertTrue(result.issuperset(match_set))
            self.assertSetEqual(result.intersection(fail_set), set())

    def test_search_name(self):
        """ Account.search() for name. """
        tests = [({'expire_start': None, 'name': a['account_name']},
                  int(a['entity_id'])) for a in self._accounts]

        assert len(tests) >= 1  # We need at least 1 group for this test
        for params, match_id in tests:
            result = self._ac.search(**params)
            self.assertEqual(len(result), 1)
            self.assertEqual(int(result[0]['account_id']), match_id)

    def test_search_name_wildcard(self):
        """ Account.search() for name with wildcards. """
        search_expr = self.account_ds.name_prefix + '%'
        result = list(self._ac.search(name=search_expr, expire_start=None))
        self.assertEqual(len(result), len(self._accounts))

        # The test group should contain names with unique prefixes, or this
        # test will fail...
        self.assertSetEqual(_set_of_ids(result), _set_of_ids(self._accounts))

    # TODO: Spread search, owner_type search

    def test_equality(self):
        """ Account __eq__ comparison. """
        self.assertGreaterEqual(len(self._accounts), 2)

        ac1 = Factory.get('Account')(self._db)
        ac1.find_by_name(self._accounts[0]['account_name'])
        ac2 = Factory.get('Account')(self._db)
        ac2.find_by_name(self._accounts[1]['account_name'])
        ac3 = Factory.get('Account')(self._db)
        ac3.find_by_name(self._accounts[0]['account_name'])

        self.assertEqual(ac1, ac3)
        self.assertNotEqual(ac1, ac2)
        self.assertNotEqual(ac2, ac3)

    def test_set_password(self):
        """ Account.set_password(). """
        self.assertGreaterEqual(len(self._accounts), 2)

        for account in self._accounts:
            password = account.get('password', 'default_password')
            self._ac.clear()
            self._ac.find_by_name(account['account_name'])
            self._ac.set_password(password)
            self._ac.write_db()
            self._ac.clear()
            self._ac.find_by_name(account['account_name'])
            self.assertTrue(self._ac.verify_auth(password))

    def test_verify_password(self):
        has_passwd = [a for a in self._accounts if a.get('password')]
        self.assertGreaterEqual(len(has_passwd), 1)

        # Password should have been set when created
        for account in has_passwd:
            self._ac.clear()
            self._ac.find_by_name(account['account_name'])
            self.assertTrue(self._ac.verify_auth(account['password']))
            self.assertFalse(self._ac.verify_auth(account['password'] + 'x'))

    def test_encrypt_verify_methods(self):
        """ Account encrypt_password and verify_password methods. """

        salt = 'somes4lt'
        password = 'ex-mpLe-p4~~'

        must_encode = ['auth_type_md5_crypt',
                       'auth_type_sha256_crypt', 'auth_type_sha512_crypt',
                       'auth_type_ssha', 'auth_type_md4_nt',
                       'auth_type_plaintext', 'auth_type_md5_unsalt',
                       'auth_type_ha1_md5', ]

        # For some reason, md4_unsalt does not verify
        must_verify = ['auth_type_md5_crypt',
                       'auth_type_sha256_crypt', 'auth_type_sha512_crypt',
                       'auth_type_ssha', 'auth_type_md4_nt',
                       'auth_type_plaintext', 'auth_type_ha1_md5', ]

        auth_type_consts = [d for d in dir(self._co) if
                            d.startswith('auth_type_')]

        self.assertTrue(set(must_encode).issubset(set(auth_type_consts)))
        self.assertTrue(set(must_verify).issubset(set(auth_type_consts)))

        for m in auth_type_consts:
            method = getattr(self._co, m)
            try:
                # We add the salt to the password, just to get a different
                # password from the unsalted test
                salted = self._ac.encrypt_password(method, salt+password, salt)
                self.assertTrue(bool(salted))
                unsalted = self._ac.encrypt_password(method, password)
                self.assertTrue(bool(unsalted))
            except Errors.NotImplementedAuthTypeError:
                self.assertNotIn(method, must_encode)
                continue
            try:
                self.assertTrue(self._ac.verify_password(method, salt+password,
                                                         salted))
                self.assertFalse(self._ac.verify_password(method, password,
                                                          salted))
                self.assertTrue(self._ac.verify_password(method, password,
                                                         unsalted))
                self.assertFalse(self._ac.verify_password(method,
                                                          salt+password,
                                                          unsalted))
            except ValueError:
                self.assertNotIn(method, must_verify)

    def test_populate_affect_auth(self):
        """ Account.populate_auth_type() and Account.affect_auth_types. """
        # populate_auth_type and affect_auth_types will always be used in
        # conjunction, and is not possible to test independently without
        # digging into the Account class implementation.
        #
        self.assertGreaterEqual(len(self._accounts), 1)

        # Tuples of (auth_method, cryptstring, try_to_affect)
        tests = [(self._co.auth_type_sha256_crypt, 'crypt-resgcsgq', False),
                 (self._co.auth_type_sha512_crypt, 'crypt-juoxpixs', True)]
        # This should change the sha-512 crypt, but not the sha-256 crypt:

        for account in self._accounts:
            self._ac.clear()
            self._ac.find_by_name(account['account_name'])

            # Populate each of the auth methods given in tests
            for method, crypt, _ in tests:
                self._ac.populate_authentication_type(method, crypt)

            # Only affect selected auth methods
            self._ac.affect_auth_types(
                *(method for method, _, affect in tests if affect))
            self._ac.write_db()
            self._ac.clear()
            self._ac.find_by_name(account['account_name'])

            # Check that only affected auth method crypts were altered
            for method, new_crypt, affect in tests:
                try:
                    crypt = self._ac.get_account_authentication(method)
                except Errors.NotFoundError:
                    # The non-affected methods may not exist in the db, but the
                    # affected method MUST exist
                    self.assertFalse(affect)
                else:
                    # The method exists in the database...
                    if affect:
                        # ...and is an affected method - the crypt must match
                        # the one we set
                        self.assertEqual(crypt, new_crypt)
                    else:
                        # ...and is not an affected method - the crypt SHOULD
                        # NOT match the one we set.
                        # NOTE: If you're reading this, it's probably because
                        # the method is plaintext, and the old crypt is the
                        # same as the one given in 'tests'...
                        self.assertNotEqual(crypt, new_crypt,
                                            msg="See test code comment...")
