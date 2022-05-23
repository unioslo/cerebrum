#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
""" Tests for the Ephorte module - Cerebrum/modules/no/uio/Ephorte.py."""
import pickle
import unittest

import mx.DateTime as DateTime

from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uio import Ephorte
from Cerebrum.testutils.datasource import BasicAccountSource
from Cerebrum.testutils.datasource import BasicPersonSource
from Cerebrum.testutils.dbtools import DatabaseTools


# TODO: Refactor all the functions.


class EphorteTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._db = Factory.get('Database')()
        cls._db.cl_init(change_program='nosetests')
        cls._db.commit = cls._db.rollback  # Let's try not to screw up the db

        cls._pe = Factory.get('Person')(cls._db)
        cls._ac = Factory.get('Account')(cls._db)
        cls._co = Factory.get('Constants')(cls._db)
        cls._er = Ephorte.EphorteRole(cls._db)
        cls._ep = Ephorte.EphortePermission(cls._db)

        cls.person_ds = BasicPersonSource()
        cls.account_ds = BasicAccountSource()
        cls.db_tools = DatabaseTools(cls._db)

    @classmethod
    def tearDownClass(cls):
        # Fast and dirty cleanup
        cls._db.execute('DELETE FROM ephorte_role')
        cls._db.execute('DELETE FROM ephorte_permission')
        cls.db_tools.clear_persons()
        cls.db_tools.clear_ous()
        cls._db.rollback()

    def tearDown(self):
        self._db.rollback()

    # Test role-related functions
    def test_add_ephorte_role(self):
        """Testing addition of ePhorte roles."""
        person_id = self.db_tools.create_person(self.person_ds().next())
        ou_id = self.db_tools.create_ou(
            {'name': 'ephorte-test',
             'acronym': 'ET',
             'short_name': 'ePhorte-test',
             'display_name': 'Test OU for ePhorte'})
        role = {'person_id': person_id,
                'adm_enhet': ou_id,
                'journalenhet': self._co.ephorte_journenhet_uio,
                'arkivdel': self._co.ephorte_arkivdel_sak_uio,
                'role_type': self._co.ephorte_role_sb,
                'standard_role': 'T',
                'auto_role': 'F',
                'stilling': '',
                'rolletittel': '',
                'start_date': None,
                'end_date': None}
        # TODO: Prettify
        self._er.add_role(
            person_id, self._co.ephorte_role_sb,
            ou_id, self._co.ephorte_arkivdel_sak_uio,
            self._co.ephorte_journenhet_uio,
            standard_role='T',
            auto_role='F')
        r = self._er.get_role(
            person_id, self._co.ephorte_role_sb,
            ou_id, self._co.ephorte_arkivdel_sak_uio,
            self._co.ephorte_journenhet_uio, standard_role='T')
        self.assertEqual(len(r), 1, 'Number of roles added not equal 1')
        self.assertEqual(dict(r[0]), role,
                         'Role added does not match role fetched')

        # Write the logged changes to the database, so we can verify them by
        # fetching them trough the API.
        self._db.commit_log()
        changes = list(
            self._db.get_log_events(
                subject_entity=person_id,
                types=self._co.ephorte_role_add))
        self.assertEqual(
            len(changes),
            1,
            'Number of changes logged not equal 1')
        self.assertEqual(
            changes[0]['dest_entity'],
            ou_id,
            'Change logged to wrong OU')
        # Note: We call str() on the constants.
        self.assertEqual(
            pickle.loads(changes[0]['change_params']),
            {'arkivdel': str(self._co.ephorte_arkivdel_sak_uio),
             'rolle_type': str(self._co.ephorte_role_sb)},
            'Change-params of role added does not match expected values')

    def test_remove_ephorte_role(self):
        """Testing removal of ePhorte roles."""
        person_id = self.db_tools.create_person(self.person_ds().next())
        account_id = self.db_tools.create_account(self.account_ds().next())
        ou_id = self.db_tools.create_ou(
            {'name': 'ephorte-test',
             'acronym': 'ET',
             'short_name': 'ePhorte-test',
             'display_name': 'Test OU for ePhorte'})
        self._er.add_role(
            person_id, self._co.ephorte_role_sb,
            ou_id, self._co.ephorte_arkivdel_sak_uio,
            self._co.ephorte_journenhet_uio,
            standard_role='T',
            auto_role='F')
        # Add a permisson to test the permission removal
        self._ep.add_permission(
            person_id, self._co.ephorte_perm_ar,
            ou_id, account_id)
        self._er.remove_role(
            person_id, self._co.ephorte_role_sb,
            ou_id, self._co.ephorte_arkivdel_sak_uio,
            self._co.ephorte_journenhet_uio)
        self.assertFalse(self._er.list_roles(person_id), 'Role not removed')

        self._db.commit_log()
        changes = list(
            self._db.get_log_events(
                subject_entity=person_id,
                types=self._co.ephorte_role_rem))
        self.assertEqual(
            len(changes),
            1,
            'Number of changes logged not equal 1')
        self.assertEqual(
            changes[0]['dest_entity'],
            ou_id,
            'Change logged to wrong OU')
        # Note: We call str() on the constants.
        self.assertEqual(
            pickle.loads(changes[0]['change_params']),
            {'arkivdel': str(self._co.ephorte_arkivdel_sak_uio),
             'rolle_type': str(self._co.ephorte_role_sb)},
            'Change-params of role removed does not match expected values')

    def test_is_standard_role(self):
        """Testing standard role check."""
        person_id = self.db_tools.create_person(self.person_ds().next())
        ou_id = self.db_tools.create_ou(
            {'name': 'ephorte-test',
             'acronym': 'ET',
             'short_name': 'ePhorte-test',
             'display_name': 'Test OU for ePhorte'})
        self._er.add_role(
            person_id, self._co.ephorte_role_sb,
            ou_id, self._co.ephorte_arkivdel_sak_uio,
            self._co.ephorte_journenhet_uio,
            standard_role='T',
            auto_role='F')
        self._er.add_role(
            person_id, self._co.ephorte_role_ar1,
            ou_id, self._co.ephorte_arkivdel_sak_uio,
            self._co.ephorte_journenhet_uio,
            standard_role='F',
            auto_role='F')
        self.assertTrue(
            self._er.is_standard_role(
                person_id, self._co.ephorte_role_sb,
                ou_id, self._co.ephorte_arkivdel_sak_uio,
                self._co.ephorte_journenhet_uio),
            'Default role not default')
        self.assertFalse(
            self._er.is_standard_role(
                person_id, self._co.ephorte_role_ar1,
                ou_id, self._co.ephorte_arkivdel_sak_uio,
                self._co.ephorte_journenhet_uio),
            'Non-default role is default')
        self.assertFalse(
            self._er.is_standard_role(
                person_id, self._co.ephorte_role_ar2,
                ou_id, self._co.ephorte_arkivdel_sak_uio,
                self._co.ephorte_journenhet_uio),
            'Non-existent role set as default')

    def test_get_role(self):
        """Testing fetching of roles."""
        person_id = self.db_tools.create_person(self.person_ds().next())
        ou_id = self.db_tools.create_ou(
            {'name': 'ephorte-test',
             'acronym': 'ET',
             'short_name': 'ePhorte-test',
             'display_name': 'Test OU for ePhorte'})
        role = {'person_id': person_id,
                'adm_enhet': ou_id,
                'journalenhet': self._co.ephorte_journenhet_uio,
                'arkivdel': self._co.ephorte_arkivdel_sak_uio,
                'role_type': self._co.ephorte_role_sb,
                'standard_role': 'T',
                'auto_role': 'F',
                'stilling': '',
                'rolletittel': '',
                'start_date': None,
                'end_date': None}
        # TODO: Prettify
        self._er.add_role(
            person_id, self._co.ephorte_role_sb,
            ou_id, self._co.ephorte_arkivdel_sak_uio,
            self._co.ephorte_journenhet_uio,
            standard_role='T',
            auto_role='F')
        r = self._er.get_role(
            person_id, self._co.ephorte_role_sb,
            ou_id, self._co.ephorte_arkivdel_sak_uio,
            self._co.ephorte_journenhet_uio, standard_role='T')
        self.assertEqual(len(r), 1, 'Number of roles added not equal one')
        self.assertEqual(dict(r[0]), role,
                         'Role added does not match role fetched')
        r = self._er.get_role(
            person_id, self._co.ephorte_role_ar1,
            ou_id, self._co.ephorte_arkivdel_sak_uio,
            self._co.ephorte_journenhet_uio, standard_role='T')
        self.assertFalse(r, 'Found role that should not be found')

    def test_list_roles(self):
        """Testing listing of roles."""
        person_id = self.db_tools.create_person(self.person_ds().next())
        person_id2 = self.db_tools.create_person(self.person_ds().next())
        ou_id = self.db_tools.create_ou(
            {'name': 'ephorte-test',
             'acronym': 'ET',
             'short_name': 'ePhorte-test',
             'display_name': 'Test OU for ePhorte'})
        self._er.add_role(
            person_id, self._co.ephorte_role_sb,
            ou_id, self._co.ephorte_arkivdel_sak_uio,
            self._co.ephorte_journenhet_uio,
            standard_role='T',
            auto_role='F')
        self._er.add_role(
            person_id2, self._co.ephorte_role_sb,
            ou_id, self._co.ephorte_arkivdel_sak_uio,
            self._co.ephorte_journenhet_uio,
            standard_role='T',
            auto_role='F')
        self.assertEqual(len(self._er.list_roles(person_id)), 1,
                         'Wrong number of roles fetched for person')
        self.assertEqual(len(self._er.list_roles()), 2,
                         'Wrong number of roles fetched')

    def test_set_standard_role_val(self):
        """Testing if setting of standard role works."""
        person_id = self.db_tools.create_person(self.person_ds().next())
        ou_id = self.db_tools.create_ou(
            {'name': 'ephorte-test',
             'acronym': 'ET',
             'short_name': 'ePhorte-test',
             'display_name': 'Test OU for ePhorte'})
        self._er.add_role(
            person_id, self._co.ephorte_role_sb,
            ou_id, self._co.ephorte_arkivdel_sak_uio,
            self._co.ephorte_journenhet_uio,
            standard_role='T',
            auto_role='F')
        self._er.set_standard_role_val(
            person_id, self._co.ephorte_role_sb,
            ou_id, self._co.ephorte_arkivdel_sak_uio,
            self._co.ephorte_journenhet_uio,
            'F')
        self.assertEqual(self._er.list_roles(person_id)[0]['standard_role'],
                         'F', 'Standard role not set')

        self._db.commit_log()
        changes = list(
            self._db.get_log_events(
                subject_entity=person_id,
                types=self._co.ephorte_role_upd))
        self.assertEqual(
            len(changes),
            1,
            'Number of changes logged not equal 1')
        self.assertEqual(
            changes[0]['dest_entity'],
            ou_id,
            'Change logged on wrong OU')
        self.assertEqual(
            pickle.loads(changes[0]['change_params']),
            {'standard_role': 'F'},
            'Change-params of role updated does not match expected values')

    # Test permission-related functions.
    def test_add_permission(self):
        """Testing if addition of permissions work."""
        person_id = self.db_tools.create_person(self.person_ds().next())
        account_id = self.db_tools.create_account(self.account_ds().next())
        ou_id = self.db_tools.create_ou(
            {'name': 'ephorte-test',
             'acronym': 'ET',
             'short_name': 'ePhorte-test',
             'display_name': 'Test OU for ePhorte'})

        self._ep.add_permission(
            person_id, self._co.ephorte_perm_ar,
            ou_id, account_id)
        self.assertTrue(
            self._ep.has_permission(
                person_id, self._co.ephorte_perm_ar, ou_id),
            'Permission not set')

        self._db.commit_log()
        changes = list(
            self._db.get_log_events(
                subject_entity=person_id,
                types=self._co.ephorte_perm_add))
        self.assertEqual(
            len(changes),
            1,
            'Number of changes logged not equal 1')
        self.assertEqual(
            changes[0]['dest_entity'],
            ou_id,
            'Change logged on wrong OU')
        self.assertEqual(
            pickle.loads(changes[0]['change_params']),
            {'perm_type': 'AR',
             'adm_enhet': ou_id},
            'Change-params of permission added does not match expected values')

    def test_remove_permission(self):
        """Testing if removal of permissions work."""
        person_id = self.db_tools.create_person(self.person_ds().next())
        account_id = self.db_tools.create_account(self.account_ds().next())
        ou_id = self.db_tools.create_ou(
            {'name': 'ephorte-test',
             'acronym': 'ET',
             'short_name': 'ePhorte-test',
             'display_name': 'Test OU for ePhorte'})

        self._ep.add_permission(
            person_id, self._co.ephorte_perm_ar,
            ou_id, account_id)
        self._ep.remove_permission(
            person_id,
            self._co.ephorte_perm_ar,
            ou_id)
        self.assertFalse(
            self._ep.list_permission(person_id),
            'Permission could not be removed')

        self._db.commit_log()
        changes = list(
            self._db.get_log_events(
                subject_entity=person_id,
                types=self._co.ephorte_perm_add))
        self.assertEqual(
            len(changes),
            1,
            'Number of changes logged not equal 1')
        self.assertEqual(
            changes[0]['dest_entity'],
            ou_id,
            'Change logged on wrong OU')
        self.assertEqual(
            pickle.loads(changes[0]['change_params']),
            {'perm_type': 'AR',
             'adm_enhet': ou_id},
            'Change-params of permission added does not match expected values')

    def test_list_permission(self):
        """Testing permission listing."""
        person_id = self.db_tools.create_person(self.person_ds().next())
        account_id = self.db_tools.create_account(self.account_ds().next())
        ou_id = self.db_tools.create_ou(
            {'name': 'ephorte-test',
             'acronym': 'ET',
             'short_name': 'ePhorte-test',
             'display_name': 'Test OU for ePhorte'})

        self.assertFalse(self._ep.list_permission(),
                         'Listed permission, should be none')

        self._ep.add_permission(
            person_id, self._co.ephorte_perm_ar,
            ou_id, account_id)
        self._ep.add_permission(
            person_id, self._co.ephorte_perm_ua,
            ou_id, account_id)

        self.assertEqual(
            self._ep.list_permission(person_id),
            [(person_id, self._co.ephorte_perm_ar, ou_id,
              account_id, DateTime.today(), None),
             (person_id, self._co.ephorte_perm_ua, ou_id,
              account_id, DateTime.today(), None)],
            'Failed listing added roles for person')
        self.assertEqual(len(self._ep.list_permission()), 2,
                         'Number of permissions listed not equal')

    def test_expire_permission(self):
        """Testing if expired test works."""
        person_id = self.db_tools.create_person(self.person_ds().next())
        account_id = self.db_tools.create_account(self.account_ds().next())
        ou_id = self.db_tools.create_ou(
            {'name': 'ephorte-test',
             'acronym': 'ET',
             'short_name': 'ePhorte-test',
             'display_name': 'Test OU for ePhorte'})

        self._ep.add_permission(
            person_id, self._co.ephorte_perm_ar,
            ou_id, account_id)
        self._ep.expire_permission(person_id, self._co.ephorte_perm_ar, ou_id)
        self.assertFalse(
            self._ep.list_permission(person_id,
                                     self._co.ephorte_perm_ar,
                                     ou_id,
                                     filter_expired=True),
            'Permission could not be expired w/o date')
        self._ep.expire_permission(person_id,
                                   self._co.ephorte_perm_ar,
                                   ou_id,
                                   DateTime.today() - 1)
        self.assertFalse(
            self._ep.list_permission(person_id,
                                     self._co.ephorte_perm_ar,
                                     ou_id,
                                     filter_expired=True),
            'Permission could not be expired with date')

        self._ep.expire_permission(person_id,
                                   self._co.ephorte_perm_ar,
                                   ou_id,
                                   DateTime.today() + 1)
        self.assertTrue(
            self._ep.list_permission(person_id,
                                     self._co.ephorte_perm_ar,
                                     ou_id,
                                     filter_expired=True),
            'Permission could not be expired with date in fututre')

    def test_has_permission(self):
        """Testing if has_permission() works."""
        # TODO: This ain't sane. has_permission returns true, if there exists
        # an expired permission.
        person_id = self.db_tools.create_person(self.person_ds().next())
        account_id = self.db_tools.create_account(self.account_ds().next())
        ou_id = self.db_tools.create_ou(
            {'name': 'ephorte-test',
             'acronym': 'ET',
             'short_name': 'ePhorte-test',
             'display_name': 'Test OU for ePhorte'})

        self._ep.add_permission(
            person_id, self._co.ephorte_perm_ar,
            ou_id, account_id)
        self.assertTrue(
            self._ep.has_permission(person_id,
                                    self._co.ephorte_perm_ar,
                                    ou_id),
            'Check for existing permission failed')

        self._ep.remove_permission(
            person_id,
            self._co.ephorte_perm_ar,
            ou_id)
        self.assertFalse(
            self._ep.has_permission(person_id,
                                    self._co.ephorte_perm_ar,
                                    ou_id),
            'Check for non-existent permission failed')
