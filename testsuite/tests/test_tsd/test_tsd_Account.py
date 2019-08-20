#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Tests for TSD's account mixin - Cerebrum/modules/tsd/Account.py.

Searching (members and groups) has to be thoroughly tested.
"""

import unittest

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.dns import DnsOwner

from datasource import BasicAccountSource, BasicPersonSource
from dbtools import DatabaseTools
from datasource import expired_filter, nonexpired_filter

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

        cls._pe = Factory.get('Person')(cls._db)
        cls._ac = Factory.get('Account')(cls._db)
        cls._gr = Factory.get('Group')(cls._db)
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

    def test_not_part_of_project(self):
        """Account should not be approved for project"""
        account_id = self.db_tools.create_account(self.account_ds().next())
        self._ac.clear()
        self._ac.find(account_id)
        self.assertFalse(self._ac.is_approved())
        self.assertRaises(Errors.NotFoundError, self._ac.get_tsd_project_id)

    @unittest.skip
    def test_unapproved_project(self):
        """Account is not approved if project is not approved."""
        raise Exception('not implemented yet')

    def test_only_one_project(self):
        """One account can only be part of *one* project."""
        # Create TSD projects:
        # TODO: This could be implemented in db_tools
        ouids = []
        self._ou.clear()
        self._ou.create_project('test1')
        ouids.append(self._ou.entity_id)
        self._ou.clear()
        pid = self._ou.create_project('test2')
        ouids.append(self._ou.entity_id)

        person_id = self.db_tools.create_person(self.person_ds().next())
        self._pe.clear()
        self._pe.find(person_id)
        for ouid in ouids:
            self._pe.populate_affiliation(
                            source_system=self._co.system_nettskjema,
                            ou_id=ouid,
                            affiliation=self._co.affiliation_project,
                            status=self._co.affiliation_status_project_member)
            self._pe.write_db()

        account = self.account_ds().next()
        account['entity_id'] = self.db_tools.create_account(account, person_id)

        self._ac.clear()
        self._ac.find(account['entity_id'])
        self._ac.set_account_type(ouids[0], self._co.affiliation_project)
        self._ac.write_db()
        self.assertRaises(Errors.CerebrumError, self._ac.set_account_type,
                          ouids[1], self._co.affiliation_project)

    def test_get_username_without_projectid(self):
        """Get username without project-ID."""
        for username, stripped in (
                ('p22-ola', 'ola'),
                ('p01-nordmann', 'nordmann'),
                # Add more formats here when the we reach p99 and changes the
                # name format.
                ('p99-ola-nordmann-hansen', 'ola-nordmann-hansen')):
            self.assertEqual(self._ac.get_username_without_project(username),
                             stripped)

    def test_setup_for_project(self):
        """Approved accounts should be set up with host and groups."""
        old_cereconf_groups = cereconf.TSD_PROJECT_GROUPS[:]
        cereconf.TSD_PROJECT_GROUPS = (
                ('member-group', 'All members', ()),)
        old_cereconf_members = cereconf.TSD_GROUP_MEMBERS.copy()
        cereconf.TSD_GROUP_MEMBERS['member-group'] = ('person_aff:PROJECT',)

        self._ou.clear()
        pid = self._ou.create_project('tsthst')
        self._ou.populate_trait(self._co.trait_project_vm_type,
                                strval='linux_vm')
        self._ou.setup_project(self.db_tools.get_initial_account_id())
        self._ou.write_db()

        # TODO: Create helper methods for this, if needed in more tests:
        person_id = self.db_tools.create_person(self.person_ds().next())
        self._pe.clear()
        self._pe.find(person_id)
        self._pe.populate_affiliation(
                            source_system=self._co.system_nettskjema,
                            ou_id=self._ou.entity_id,
                            affiliation=self._co.affiliation_project,
                            status=self._co.affiliation_status_project_member)
        self._pe.write_db()

        account = self.account_ds().next()
        account_id = self.db_tools.create_account(account, person_id)
        self._ac.clear()
        self._ac.find(account_id)
        self._ac.set_account_type(self._ou.entity_id,
                                  self._co.affiliation_project)
        self._ac.write_db()
        self._ac.setup_for_project()
        # Check data
        dnsowner = DnsOwner.DnsOwner(self._db)
        # User should have its own host:
        dnsowner.find_by_name('%s-l.tsd.usit.no.' % self._ac.account_name)

        # User should be member of some groups:
        for grname in ('member-group',):
            self._gr.clear()
            self._gr.find_by_name('-'.join((pid, grname)))
            #self.assertTrue(self._gr.has_member(self._ac.entity_id))

        # TODO: This should rather be in the teardown, to avoid trouble in later
        # tests:
        cereconf.TSD_PROJECT_GROUPS = old_cereconf_groups
        cereconf.TSD_GROUP_MEMBERS = old_cereconf_members
