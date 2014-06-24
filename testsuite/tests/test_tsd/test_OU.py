#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
""" Tests for TSD's OU mixin - Cerebrum/modules/tsd/OU.py.

Each TSD project is represented by an OU.

"""

import unittest2 as unittest

from mx import DateTime

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import dns

from datasource import BasicAccountSource, BasicPersonSource
from dbtools import DatabaseTools
from datasource import expired_filter, nonexpired_filter

class TSDOUTest(unittest.TestCase):

    """ This is a testcase for TSD's OU class.

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

        cls._pe = Factory.get('Person')(cls._db)
        cls._ac = Factory.get('Account')(cls._db)
        cls._ou = Factory.get('OU')(cls._db)
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
        cls.db_tools.clear_ous()
        cls._db.rollback()

class SimpleOUTests(TSDOUTest):

    """ Test case for simple scenarios. """

    def test_create_project(self):
        """Create a simple project OU."""
        self._ou.clear()
        pid = self._ou.create_project('tstcr2')
        eid = self._ou.entity_id
        self.assertTrue(eid > 0)

        self._ou.clear()
        self._ou.find_by_tsd_projectid(pid)

        self._ou.clear()
        self._ou.find(eid)
        self.assertEqual(self._ou.get_project_id(), pid)

    def test_setup_project(self):
        """Setup a full project"""
        self._ou.clear()
        self._ou.create_project('tstcr')
        # Add various settings:
        self._ou.populate_trait(self._co.trait_project_vm_type,
                                strval='win_and_linux_vm')
        self._ou.write_db()
        self._ou.setup_project(self.db_tools.get_initial_account_id())

        # TODO: Check for host, groups, etc
        #self.assertTrue(

    @unittest.skip
    def test_quarantined_project(self):
        """Quarantined projects should not be set up."""
        self._ou.clear()
        self._ou.create_project('tstcr')
        # Add various settings:
        self._ou.populate_trait(self._co.trait_project_vm_type,
                                strval='win_and_linux_vm')
        # Add quarantine:
        self._ou.add_entity_quarantine(
                type=self._co.quarantine_not_approved,
                creator=self.db_tools.get_initial_account_id(),
                description='Project not approved yet',
                start=DateTime.now())
        self._ou.write_db()
        self._ou.setup_project(self.db_tools.get_initial_account_id())
        # TODO: Check that nothing has been setup!

