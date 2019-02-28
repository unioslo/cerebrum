#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2014-2016 University of Oslo, Norway
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

""" Basic tests for the AD2 sync.

Testing that the basic, generic functionality works as expected, e.g. standard
behaviour of creating, moving and removing AD objects, and the generic
configuration of attributes.

"""
import base64
import pickle
import random
import string
import unittest

import cereconf

from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum import Constants
from Cerebrum.Utils import Factory, read_password
from Cerebrum.utils.gpg import gpgme_decrypt
from datasource import BasicAccountSource, BasicPersonSource
from dbtools import DatabaseTools
from datasource import expired_filter, nonexpired_filter

from Cerebrum.modules.ad2 import ADSync, ADUtils


def read_password_catcher(user, system, host=None):
    """Override to ignore missing password files.

    This is since we're in test don't need the password to other systems.

    """
    try:
        return read_password(user, system, host)
    except IOError:
        return 'random9'

Utils.read_password = read_password_catcher
ADUtils.read_password = read_password_catcher


class MockADclient(ADUtils.ADclient):
    """ Mock AD client, to avoid trying to talk with AD.

    """
    def __init__(self, *args, **kwargs):
        """Override to avoid trying to connect to some AD server."""
        # TODO: get the cls._db from test!
        pass


class BaseAD2SyncTest(unittest.TestCase):

    """ Testcase for Cerebrum.modules.ad2.ADSync.BaseSync class.

    TODO: More information

    """

    @classmethod
    def setUpClass(cls):
        """ Setting up the TestCase module.

        The AD sync needs to be set up with standard configuration.
        """
        cls._db = Factory.get('Database')()
        cls._db.cl_init(change_program='nosetests')
        cls._db.commit = cls._db.rollback  # Let's try not to screw up the db
        cls._co = Factory.get('Constants')(cls._db)
        cls._ac = Factory.get('Account')(cls._db)
        cls._gr = Factory.get('Group')(cls._db)

        # Data sources
        cls.account_ds = BasicAccountSource()
        cls.person_ds = BasicPersonSource()

        # Tools for creating and destroying temporary db items
        cls.db_tools = DatabaseTools(cls._db)

        # Add some constanst for the tests
        cls.const_spread_ad_user = cls.db_tools.insert_constant(
            Constants._SpreadCode, 'account@ad_test',
            cls._co.entity_account, 'User in test AD')
        cls.const_spread_ad_group = cls.db_tools.insert_constant(
            Constants._SpreadCode, 'group@ad_test',
            cls._co.entity_group, 'Group in test AD')

        # Creating a sample config to be tweaked on in the different test cases
        # Override for the different tests.
        cls.standard_config = {
            'sync_type': 'test123',
            'domain': 'nose.local',
            'server': 'localserver',
            'target_ou': 'OU=Cerebrum,DC=nose,DC=local',
            'search_ou': 'OU=Cerebrum,DC=nose,DC=local',
            'object_classes': (
                'Cerebrum.modules.ad2.CerebrumData/CerebrumEntity',),
            'target_type': cls._co.entity_account,
        }
        # Make sure every reuquired setting is in place:
        for var in ADSync.BaseSync.settings_required:
            if var not in cls.standard_config:
                cls.standard_config[var] = 'random'
        # Override the AD client with a mock client:
        ADSync.BaseSync.server_class = MockADclient
        # Force in an object type in the Base class. The BaseSync should not
        # work, only its subclasses, but we want to be able to test the basic
        # functionality:
        ADSync.BaseSync.default_ad_object_class = 'object'

    @classmethod
    def tearDownClass(cls):
        """ Clean up the TestCase. """
        cls.db_tools.clear_groups()
        cls.db_tools.clear_accounts()
        cls.db_tools.clear_persons()
        cls.db_tools.clear_constants()
        cls._db.rollback()

    def get_adsync_object(self, classes, config):
        """Return a AD2 sync object ready for use, but mocked up.

        :type classes: list or tuple of str
        :param classes:
            A list of what classes to use for the sync object. All elements
            must be subclassed from BaseSync.

        :type config: dict
        :param config: The dict to setup with the sync object.

        :rtype: Cerebrum.modules.ad2.ADSync.BaseSync
        :return: The instantiated sync class by given configuration.
        """
        sync_class = ADSync.BaseSync.get_class(classes=classes)
        sync_class.server_class = MockADclient
        sync = sync_class(self._db, Factory.get_logger('console'))
        sync.configure(config)
        return sync

    # TODO: Create more helper methods


class SimpleAD2SyncTest(BaseAD2SyncTest):
    """ The test cases for the basic AD sync. """
    # The default sync class to use in this testcase:
    base_sync = ['Cerebrum.modules.ad2.ADSync/BaseSync']

    def test_setup(self):
        """Basic sync should be set up with default settings."""
        self.sync = self.get_adsync_object(self.base_sync,
                                           self.standard_config)
        self.assertIsInstance(self.sync.server, MockADclient)

    # TODO: Test rest of the setup of the AD2 sync


class UserAD2SyncTest(BaseAD2SyncTest):
    """ The test cases that are specific to Accounts. """
    # The default sync class to use in this testcase:
    base_sync = ['Cerebrum.modules.ad2.ADSync/UserSync']

    # The default object class to use in this testcase:
    object_classes = ['Cerebrum.modules.ad2.CerebrumData/CerebrumUser']

    def setUp(self):
        """ Prepare test.

        Sets up some test candidates and the sync itself.
        """
        uni_chars = unicode(string.ascii_letters) + unicode(string.digits)
        # generate a random 32 characters long unicode string and then append
        # 'æøå' in order to provoke some errors
        random_prefix = u''.join(random.choice(uni_chars) for _ in range(32))
        self.rnd_password_unicode = random_prefix + 'æøå'.decode('utf-8')
        self.rnd_password_str = self.rnd_password_unicode.encode('utf-8')

        person_id = self.db_tools.create_person(
            self.person_ds.get_next_item())
        self.addCleanup(self.db_tools.delete_person_id, person_id)

        self._accounts = []
        for account in self.account_ds(limit=10):
            entity_id = self.db_tools.create_account(
                account, person_owner_id=person_id)
            account['entity_id'] = entity_id
            self._accounts.append(account)
            self.addCleanup(self.db_tools.delete_account_id, entity_id)
        for account in self._accounts:
            self._ac.clear()
            self._ac.find(account['entity_id'])
            self._ac.add_spread(self.const_spread_ad_user)
        # Setup the sync
        conf = self.standard_config.copy()
        conf['object_classes'] = self.object_classes
        conf['target_spread'] = self.const_spread_ad_user
        self.sync = self.get_adsync_object(self.base_sync, conf)

    @unittest.skip("Not implemented yet")
    def test_create_user(self):
        """Create an AD object"""
        self.sync.fetch_cerebrum_data()

        # TODO:
        # 1. Run the fullsync
        # self.sync..fullsync()
        # 2. Feed the sync with an empty list from AD. Needs mocking.
        # 3. Assert that the MockADclient gets a call to create_object with
        #    correct parameters. Find out how unittest supports asserting
        #    IsCalled.

    def test_fetched_users(self):
        """Fetch correct entities from Cerebrum"""
        # The number of users that should be targetet by the sync:
        users_to_target = 10
        person_id = self.db_tools.create_person(
            self.person_ds.get_next_item())
        self.addCleanup(self.db_tools.delete_person_id, person_id)
        # Add some accounts with spread:
        yes_ids = []
        for account in self.account_ds(limit=users_to_target):
            # TODO: Maybe we should be able to get an Account object from the
            # db_tools function, if further modification is needed?
            account_id = self.db_tools.create_account(
                account, person_owner_id=person_id)
            ac = self.db_tools.get_account_object()
            # TODO: This fails for some of the entities! Why???
            ac.add_spread(self.const_spread_ad_user)
            ac.write_db()
            self.addCleanup(self.db_tools.delete_account_id, account_id)
            yes_ids.append(account_id)
        # Add some accounts without the spread:
        no_ids = []
        for account in self.account_ds(limit=5):
            account_id = self.db_tools.create_account(
                account, person_owner_id=person_id)
            self.addCleanup(self.db_tools.delete_account_id, account_id)
            no_ids.append(account_id)
        # Make the sync fetch data from Cerebrum:
        self.sync.fetch_cerebrum_data()
        # Check what the sync has found:
        self.assertEqual(users_to_target, len(self.sync.entities))
        self.assertEqual(users_to_target, len(self.sync.id2entity))
        for i in yes_ids:
            self.assertIn(i, self.sync.id2entity)
        for i in no_ids:
            self.assertNotIn(i, self.sync.id2entity)

    def test_password_gpgme_encrypt(self):
        """
        Test GnuPG and plaintext passwords
        """
        for account in self._accounts:
            self._ac.clear()
            self._ac.find(account['entity_id'])
            self._ac.set_password(self.rnd_password_str)
            self._ac.write_db()
            passwd_events = filter(
                lambda x: bool(
                    x['subject_entity'] == self._ac.entity_id and
                    x['change_type_id'] == self._co.account_password),
                self._db.messages)
            self.assertTrue(bool(passwd_events),
                            'No password event registered')
            self.assertIn('change_params',
                          passwd_events[0],
                          'No change_params in password event')
            change_params = pickle.loads(passwd_events[-1]['change_params'])
            self.assertIsInstance(change_params,
                                  dict,
                                  'change_params is not a dictionary')
            self.assertIn('password',
                          change_params,
                          'No password-key in change_params')
            stored_password = change_params['password']
            if hasattr(cereconf, 'PASSWORD_GPG_RECIPIENT_ID'):
                # tests when encryption should be performed
                self.assertTrue(stored_password.startswith('GPG:'),
                                'Password not encrypted')
                # test decryption
                self.assertEqual(
                    gpgme_decrypt(base64.b64decode(stored_password[4:])),
                    self.rnd_password_str,
                    'Unable to decrypt password "{0}" != "{1}"'.format(
                        gpgme_decrypt(stored_password),
                        self.rnd_password_str))
            else:
                # tests when no encryption is performed
                self.assertIn(self.rnd_password_str,
                              stored_password,
                              'Password not stored')

    @unittest.skip("Not done yet")
    def test_move_object(self):
        """Move an AD object to another OU in AD."""
        # We target a user
        person_id = self.db_tools.create_person(
            self.person_ds.get_next_item())
        self.addCleanup(self.db_tools.delete_person_id, person_id)
        account = self.account_ds.get_next_item()
        account_id = self.db_tools.create_account(
            account, person_owner_id=person_id)
        account['entity_id'] = account_id
        self.addCleanup(self.db_tools.delete_account_id, account_id)

        # TODO: We could move some of this to various helper methods, but not
        # sure exactly what is beneficial quite yet.

        # Start the fullsync
        self.sync.fetch_cerebrum_data()
        # TODO:
        # 1. Give input to simulate the response from AD:
        # 2. Assert that the MockADServer.move_object is called, and is given
        # the correct location.
        #
        # self.assert
