#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""Tests for TSD's OU mixin - Cerebrum/modules/tsd/OU.py.

Each TSD project is represented by an OU.
"""

import unittest

from mx import DateTime

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.dns import Subnet, IPv6Subnet
from Cerebrum.modules.dns import Errors as dnsErrors
from Cerebrum.modules.EntityTrait import EntityTrait

from datasource import BasicAccountSource, BasicPersonSource
from dbtools import DatabaseTools


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


class SimpleOUTests(TSDOUTest):
    """Test case for simple scenarios."""

    def setUp(self):
        # Save the previous values from cereconf, to add them back in when done
        self._cereconfvalues = cereconf.__dict__

    def tearDown(self):
        # Add the old cereconf values back in:
        for k, v in self._cereconfvalues.items():
            setattr(cereconf, k, v)

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
        # self.assertTrue(

    def test_filling_project_ids(self):
        """Next free project id should always be lowest unused id."""
        pid1 = self._ou.get_next_free_project_id()
        pid2 = self._ou.get_next_free_project_id()
        self.assertEqual(pid1, pid2)
        # Test that no lower project existst
        for i in range(1, int(pid1[1:])):
            self._ou.clear()
            self._ou.find_by_tsd_projectid(i)

        # set up a pair of projects, delete, and assert that project id is
        # reused
        self.setup_project("fillid1")
        id1 = self._ou.entity_id
        self.assertEqual(self._ou.get_project_id(), pid2)
        self.setup_project("fillid2")
        self._ou.clear()
        self._ou.find(id1)
        # Reject project == terminate + delete
        self._ou.terminate()
        self._ou.delete()
        self.assertEqual(self._ou.get_next_free_project_id(), pid2)

    def test_setup_101_projects(self):
        """With new logic for more than 100 projects, setup 101"""
        vlan = self._ou.get_next_free_vlan()
        for i in range(101):
            self.setup_project("seq%s" % i, vlan)

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
            qtype=self._co.quarantine_not_approved,
            creator=self.db_tools.get_initial_account_id(),
            description='Project not approved yet',
            start=DateTime.now())
        self._ou.write_db()
        self._ou.setup_project(self.db_tools.get_initial_account_id())
        # TODO: Check that nothing has been setup!

    def setup_project(self, name, vlan=None):
        """Helper for standard setup of a project.

        `self._ou` is used for the project.

        :param str name: The project name.

        """
        self._ou.clear()
        pid = self._ou.create_project(name)
        self._ou.setup_project(self.db_tools.get_initial_account_id(),
                               vlan=vlan)

    def get_project_vlans(self, ou):
        """Return a set with a project's VLANs."""
        subnet = Subnet.Subnet(self._db)
        subnet6 = IPv6Subnet.IPv6Subnet(self._db)
        vlans = set()
        for row in ou.get_project_subnets():
            if row['entity_type'] == self._co.entity_dns_subnet:
                subnet.clear()
                subnet.find(row['entity_id'])
                self.assertTrue(subnet.vlan_number)
                vlans.add(subnet.vlan_number)
            else:
                subnet6.clear()
                subnet6.find(row['entity_id'])
                self.assertTrue(subnet6.vlan_number)
                vlans.add(subnet6.vlan_number)
        return vlans

    def test_calculate_subnets_for_project(self):
        """
        Subnets for projects with ID 0-32767 should be automatically generated.
        """
        # project_id=0
        self.assertEqual(
            ('10.128.0.0/24', 'fd00:c0de:cafe:8000::/64'),
            self._ou._generate_subnets_for_project_id(0))

        # project_id=3000
        self.assertEqual(
            ('10.139.184.0/24', 'fd00:c0de:cafe:8bb8::/64'),
            self._ou._generate_subnets_for_project_id(3000))

        # project_id=32767
        self.assertEqual(
            ('10.255.255.0/24', 'fd00:c0de:cafe:ffff::/64'),
            self._ou._generate_subnets_for_project_id(32767))

    def test_calculate_subnets_for_project_out_of_range(self):
        """Generating a subnet for a project with ID > 32767 should fail."""
        # project_id=100000
        self.assertRaises(
            Errors.CerebrumError,
            self._ou._generate_subnets_for_project_id, 100000)

    def test_project_termination(self):
        """Terminated projects should remove its attributes."""
        entity_trait = EntityTrait(self._db)
        self.setup_project('del_me')
        eid = self._ou.entity_id
        self._ou.terminate()
        self.assertEqual(eid, self._ou.entity_id)
        # The OU object itself must remain, and its project ID and project name
        # No accounts:
        self.assertEqual(0, len(self._ac.list_accounts_by_type(
            ou_id=eid,
            filter_expired=False)))
        # No affiliated persons:
        self.assertEqual(0, len(self._pe.list_affiliations(
            ou_id=eid,
            include_deleted=True)))
        # Checking for different types of traits.
        # Are there any traits that should be left?
        # No groups:
        # list_traits returns an iterator instead of a list
        groups = tuple(self._gr.list_traits(
            code=self._co.trait_project_group, target_id=eid))
        self.assertEqual(0, len(groups))
        # No hosts:
        hosts = tuple(entity_trait.list_traits(
            target_id=eid, code=self._co.trait_project_host))
        self.assertEqual(0, len(hosts))
        # No subnets:
        subnets = tuple(entity_trait.list_traits(
            target_id=eid,
            code=(self._co.trait_project_subnet6,
                  self._co.trait_project_subnet)))
        self.assertEqual(0, len(subnets))
        # TODO: No project data, like names, addresses, spreads etc.

    def test_new_project_auto_vlan(self):
        """New projects should get an unused VLAN."""
        cereconf.VLAN_RANGES = ((100, 110),)
        for pr in ('auto1', 'auto2', 'auto3'):
            self.setup_project(pr)
            vlans = self.get_project_vlans(self._ou)
            self.assertEqual(1, len(vlans))
            for vlan in vlans:
                self.assertTrue(vlan >= 100)
                self.assertTrue(vlan < 110)

    def test_new_project_empty_vlans(self):
        """Can't create projects with auto VLAN when no more VLANs"""
        cereconf.VLAN_RANGES = ((200, 201),)
        # First two should work:
        self.assertTrue(self._ou.get_next_free_vlan() >= 200)
        self.setup_project('empty1')
        self.assertTrue(self._ou.get_next_free_vlan() >= 200)
        self.setup_project('empty2')
        # Should now not be more available VLANs and would fail:
        self.assertRaises(Errors.CerebrumError, self._ou.get_next_free_vlan)
        self.assertRaises(Errors.CerebrumError, self.setup_project, 'empty3')

    def test_new_project_bad_vlan(self):
        """Can't set unavailable VLANs."""
        cereconf.VLAN_RANGES = ((100, 110),)
        self.assertRaises(Errors.CerebrumError, self.setup_project, 'bvlan1',
                          vlan=90)
        self.assertRaises(Errors.CerebrumError, self.setup_project, 'bvlan3',
                          vlan='hellu')

    def test_new_project_reuse_vlan(self):
        """Two projects could share the same VLAN."""
        cereconf.VLAN_RANGES = ((100, 110),)
        # subnet = Subnet.Subnet(self._db)
        # subnet6 = IPv6Subnet.IPv6Subnet(self._db)

        self.setup_project('reuse1', vlan=105)
        # This should not fail:
        self.setup_project('reuse2', vlan=105)
        # TODO: Test that the data is okay
        # TODO: Test that the first project's data is unchanged

    @unittest.skip
    def test_new_project_subnet_overlap(self):
        """New projects must not overlap in subnets."""
        self.setup_project('subn1')
        # TODO: Create a subnet that would be in the new project's area, and
        # affiliate it with subn1
        # TODO: Assert that it fails
        self.assertRaises(dnsErrors.SubnetError, self.setup_project, 'subn2')
