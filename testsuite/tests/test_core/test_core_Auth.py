#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Basic tests for Cerebrum/Account.py.

Searching (members and groups) has to be thoroughly tested.
"""
from __future__ import unicode_literals

import logging
import unittest

from Cerebrum.Utils import Factory
from Cerebrum.Account import Account
from Cerebrum.auth import Auth

from datasource import BasicAccountSource, BasicPersonSource
from dbtools import DatabaseTools

logger = logging.getLogger(__name__)

# TODO:
#
# Not imploemented tests for
#  - Account/AccountType
#  - Account/AccountHome


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


class SimpleAuthImplementationTest(BaseAccountTest):
    """ This is a test case for simple SHA-1 hashing implementation. """

    def test_auth_ssha(self):
        auth_methods = self._co.get_system_auth_methods()
        method_name = "SSHA"
        if method_name not in auth_methods:
            return
        auth_map = Auth.AuthMap()
        methods = auth_map.get_crypt_subset(auth_methods)
        method = methods[method_name]()
        _hash = method.encrypt("hesterbest", salt="ABCDEFGI")
        self.assertEqual(
            _hash, "qBVr/e8BtH7dw2h09V8WL0jxEaxBQkNERUZHSQ==")

    def test_auth_sha256(self):
        auth_methods = self._co.get_system_auth_methods()
        method_name = "SHA-256-crypt"
        if method_name not in auth_methods:
            return
        auth_map = Auth.AuthMap()
        methods = auth_map.get_crypt_subset(auth_methods)
        method = methods[method_name]()
        _hash = method.encrypt_password("hesterbest", salt="$5$ABCDEFGI")
        logger.info(_hash)
        self.assertEqual(
            _hash, "$5$ABCDEFGI$wRL35zTjgAhecyc9CWv5Id.qsz5RZqXvDD3EXmlkUJ4")

    def test_auth_sha512(self):
        methods = get_crypt_methods()
        method = methods["auth_type_sha512"]()
        _hash = method.encrypt_password("hesterbest", salt="$6$ABCDEFGI")
        logger.info(_hash)
        self.assertEqual(
            _hash, "$6$ABCDEFGI$s5rS3hTF2FJrqxToloyKaOcmUwFMVvEft"
            "Yen3WjaetYz726AFZQkI572G0o/bO9BWC86Sae1QjMUe7TZYBeYg1")

    def test_auth_md5(self):
        methods = get_crypt_methods()
        method = methods["auth_type_md5"]()
        _hash = method.encrypt_password("hesterbest", salt="$1$ABCDEFGI")
        self.assertEqual(
            _hash, "$1$ABCDEFGI$iO4CKjwcmvejNZ7j1MEW./")

    def test_auth_md4_nt(self):
        methods = get_crypt_methods()
        method = methods["auth_type_md4_nt"]()
        _hash = method.encrypt_password("hesterbest", salt="ABC")
        self.assertEqual(
            _hash, "5DDE3A6B19D3DEB6B63E304A5574A193")
