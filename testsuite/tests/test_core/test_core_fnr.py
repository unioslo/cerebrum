# -*- coding: utf-8 -*-
""" Basic tests for Cerebrum/Account.py.

Searching (members and groups) has to be thoroughly tested.
"""
from __future__ import unicode_literals

import logging
import unittest

from Cerebrum.Utils import Factory
from Cerebrum.Account import Account

from Cerebrum.modules.no import fodselsnr as fnr

from datasource import BasicAccountSource, BasicPersonSource
from dbtools import DatabaseTools


logger = logging.getLogger(__name__)


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


class SimpleFNRTest(BaseAccountTest):

    def test_fnr(self):
        get_all_entities = """ select eei.external_id from entity_external_id eei, entity_info ei
        where ei.entity_id = eei.entity_id and
              ei.entity_type = 102 and
                    eei.id_type = 16;
        """
        unvalid_fnr = []
        total_passed = 0
        foo = self._db.query(get_all_entities)
        for x in foo:
            try:
                fnr.personnr_ok(int(x[0]))
            except:
                unvalid_fnr.append(int(x[0]))
            total_passed += 1

        logger.error(unvalid_fnr)
        logger.error("Total unvalid fnr: {}".format(len(unvalid_fnr)))
        logger.error("Total _valid_ fnr: {}".format(total_passed))
