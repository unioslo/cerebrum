#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
""" Tests for TSD's account mixin - Cerebrum/modules/tsd/Account.py.

Searching (members and groups) has to be thoroughly tested.

"""

import unittest2 as unittest

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.Account import Account
from datasource import BasicAccountSource, BasicPersonSource
from dbtools import DatabaseTools
from datasource import expired_filter, nonexpired_filter

# Simple lamda-function to create a set of account_ids/entity_ids from a
# sequence of dicts (or dict-like objects).
# Lookup order is 'entity_id' -> 'account_id'. If none of the keys exist or
# if a key exist but doesn't have an intval, a ValueError is raised.
_set_of_ids = lambda accs: \
    set((int(a.get('entity_id', a.get('account_id'))) for a in accs))


class TSDAccountTest(unittest.TestCase):

    """ This is a testcase for TSD's Account class.

    """

    @classmethod
    def setUpClass(cls):
        """ Set up this TestCase module.

        This setup code sets up shared objects between each tests. This is done
        *once* before running any of the tests within this class.

        """

        # TODO: We might want this basic class setup in other TestCases. Maybe
        #       set up a generic TestCase class to inherit common stuff from?
        cls._db = Factory.get('Database')()
        cls._db.cl_init(change_program='nosetests')
        cls._db.commit = cls._db.rollback  # Let's try not to screw up the db

        cls._ac = Factory.get('Account')(cls._db)
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


class SimpleAccountsTest(TSDAccountTest):

    """ This is a test case for simple scenarios. """

    def test_account_otpkey_length(self):
        """The OTP must be of the correct length."""
        for bytes, expected_len in ((31, 4),
                                    (32, 4),
                                    (33, 5),
                                    (191, 24),
                                    (192, 24),
                                    (193, 25),
                                    ):
            key = self._ac._generate_otpkey(bytes)
            self.assertEqual(len(key), expected_len)
