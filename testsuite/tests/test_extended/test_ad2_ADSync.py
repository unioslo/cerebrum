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
import logging
import pickle
import sys
import types

import pytest

import datasource  # testsuite/testtools/

import Cerebrum.config.adconf
from Cerebrum import Account
from Cerebrum import Person
from Cerebrum import Utils
from Cerebrum.logutils.loggers import CerebrumLogger
from Cerebrum.modules.ad2 import ADUtils
from Cerebrum.utils.gpg import gpgme_decrypt

person_cls = Person.Person
account_cls = Account.Account


def read_password_catcher(*args, **kwargs):
    """Override to ignore missing password files."""
    return 'random9'


# TODO: This patching should be done in the test or in a fixture, using a
# monkeypatch context
Utils.read_password = read_password_catcher
ADUtils.read_password = read_password_catcher


@pytest.fixture(autouse=True)
def adconf():
    """ 'adconf' config module.

    This fixture allows test modules to change settings when certain settings
    need to be tested, or when certain changes needs to be injected in the
    config.

    Note that you'll have to ensure that whatever *uses* an adconf value is
    is patched to use this fixture!  This fixture only ensures that an adconf
    exists with a minimal set of settings, and that it is reset, in case a
    fixture wants to alter it.

    TODO: Would it be better to somehow add a minimal adconf to sys.path and
    monkey patch into all imports?
    """
    adconf_module = types.ModuleType('adconf',
                                     """Mocked adconf for tests""")
    no_adconf = object()
    old_adconf = sys.modules.get('adconf', no_adconf)

    setattr(adconf_module, 'SYNCS', dict(Cerebrum.config.adconf.SYNCS))
    setattr(adconf_module, 'ConfigUtils', Cerebrum.config.adconf.ConfigUtils)

    sys.modules['adconf'] = adconf_module
    yield adconf_module

    if old_adconf is no_adconf:
        del sys.modules['adconf']
    else:
        sys.modules['adconf'] = old_adconf


@pytest.fixture
def adsync_mod(adconf):
    """ adconf fixture must be applied before importing """
    sync_module = __import__('Cerebrum.modules.ad2.ADSync',
                             fromlist=('Cerebrum', 'modules', 'ad2'))

    # monkey patch context?

    return sync_module


@pytest.fixture
def account_ds():
    return datasource.BasicAccountSource()


@pytest.fixture
def person_ds():
    return datasource.BasicPersonSource()


@pytest.fixture
def spread_code_cls(constant_module):
    return getattr(constant_module, '_SpreadCode')


@pytest.fixture
def ad_user_spread(spread_code_cls, const):
    code = spread_code_cls('adaf1d52f6d45acd',
                           str(const.entity_account),
                           description='test spread for ad users')
    code.insert()
    return code


@pytest.fixture
def ad_group_spread(spread_code_cls, const):
    code = spread_code_cls('be59b5e1d3b05fba',
                           str(const.entity_group),
                           description='test spread for ad groups')
    code.insert()
    return code


@pytest.fixture
def ad_config(adsync_mod, const):
    config = {
        'sync_type': 'unit-tests',
        'domain': 'localhost',
        'server': 'localserver',
        'target_ou': 'OU=Cerebrum,DC=nose,DC=local',
        'search_ou': 'OU=Cerebrum,DC=nose,DC=local',
        'object_classes': (
            'Cerebrum.modules.ad2.CerebrumData/CerebrumEntity',
        ),
    }

    # Make sure every reuquired setting is in place:
    for name in adsync_mod.BaseSync.settings_required:
        if name not in config:
            config[name] = 'not set -- update ad_config fixture?'
    return config


class MockADclient(ADUtils.ADclient):
    """ Mock AD client, to avoid trying to talk with AD.

    """
    def __init__(self, *args, **kwargs):
        """Override to avoid trying to connect to some AD server."""
        # TODO: get the cls._db from test!
        pass


@pytest.fixture
def logger():
    CerebrumLogger.install()
    return logging.getLogger(__name__)


def _build_sync(sync_cls, db, logger, config):
    sync_cls.server_class = MockADclient
    sync_cls.default_ad_object_class = 'object'
    sync = sync_cls(db, logger)
    sync.configure(config)
    return sync


@pytest.fixture
def base_sync(adsync_mod, database, logger, ad_config, const):
    classes = ['Cerebrum.modules.ad2.ADSync/BaseSync']
    cls = adsync_mod.BaseSync.get_class(classes=classes)

    # must have target_type or target_spread
    ad_config['target_type'] = str(const.entity_account)
    return _build_sync(cls, database, logger, ad_config)


@pytest.fixture
def user_sync(adsync_mod, database, logger, ad_config, ad_user_spread):
    classes = ['Cerebrum.modules.ad2.ADSync/UserSync']
    cls = adsync_mod.BaseSync.get_class(classes=classes)
    object_classes = ['Cerebrum.modules.ad2.CerebrumData/CerebrumUser']
    ad_config['target_spread'] = str(ad_user_spread)
    ad_config['object_classes'] = object_classes
    sync = _build_sync(cls, database, logger, ad_config)
    return sync


def test_base_sync_type(base_sync):
    assert isinstance(base_sync.server, MockADclient)


@pytest.fixture
def person_creator(database, const, person_ds):

    def _create_persons(limit=1):
        for person_dict in person_ds(limit=limit):
            person = person_cls(database)
            gender = person_dict.get('gender')
            if gender:
                gender = const.human2constant(gender, const.Gender)
            gender = gender or const.gender_unknown

            person.populate(person_dict['birth_date'],
                            gender,
                            person_dict.get('description'))
            person.write_db()
            person_dict['entity_id'] = person.entity_id
            yield person, person_dict

    return _create_persons


@pytest.fixture
def account_creator(database, const, account_ds, initial_account):
    creator_id = initial_account.entity_id

    def _create_accounts(owner, limit=1):
        owner_id = owner.entity_id
        owner_type = owner.entity_type

        for account_dict in account_ds(limit=limit):
            account_dict['expire_date'] = None

            account = account_cls(database)
            if owner_type == const.entity_person:
                account_type = None
            else:
                account_type = const.account_program

            account.populate(account_dict['account_name'],
                             owner_type,
                             owner_id,
                             account_type,
                             creator_id,
                             account_dict.get('expire_date'))
            if account_dict.get('password'):
                account.set_password(account_dict.get('password'))
            account.write_db()
            account_dict['entity_id'] = account.entity_id
            yield account, account_dict

    return _create_accounts


@pytest.fixture
def person(person_creator):
    person, _ = next(person_creator(limit=1))
    return person


@pytest.fixture
def ad_accounts(account_creator, person, ad_user_spread):
    """ list of dicts with existing personal account data. """
    accounts = []
    for account, _ in account_creator(person, limit=5):
        account.add_spread(ad_user_spread)
        accounts.append(account)
    return accounts


@pytest.fixture
def ad_account(account_creator, person, ad_user_spread):
    """ list of dicts with existing personal account data. """
    account, _ = next(account_creator(person, limit=1))
    account.add_spread(ad_user_spread)
    account.expire_date = None
    account.write_db()
    return account


@pytest.mark.skip(reason="not implemented yet")
def test_create_user(user_sync):
    """Create an AD object"""
    user_sync.fetch_cerebrum_data()


def test_fetched_users(user_sync, person, account_creator, ad_user_spread):
    """Fetch correct entities from Cerebrum"""
    # The number of users that should be targetet by the sync:
    users_to_target = 10
    # Add some accounts with spread:
    yes_ids = []
    for ac, account in account_creator(person, limit=users_to_target):
        ac.add_spread(ad_user_spread)
        ac.write_db()
        yes_ids.append(ac.entity_id)
    # Add some accounts without the spread:
    no_ids = []
    for ac, account in account_creator(person, limit=5):
        no_ids.append(ac.entity_id)

    # Make the sync fetch data from Cerebrum:
    user_sync.fetch_cerebrum_data()

    # Check what the sync has found:
    assert len(user_sync.entities) == users_to_target
    assert len(user_sync.id2entity) == users_to_target
    assert set(user_sync.id2entity) == set(yes_ids)
    assert all(eid not in set(user_sync.id2entity) for eid in no_ids)


@pytest.mark.skip(reason='needs gpg fixtures')
def test_password_gpgme_encrypt(cereconf, database, const, ad_account):
    """
    Test GnuPG and plaintext passwords
    """
    # Note: Requires old cl implementation
    password_str = u'some password'
    ac = ad_account
    ac.set_password(password_str)
    ac.write_db()
    passwd_events = filter(
        lambda x: bool(
            x['subject_entity'] == ac.entity_id and
            x['change_type_id'] == const.account_password),
        database.messages)
    assert bool(passwd_events)  # or no password events registered
    assert 'change_params' in passwd_events[-1]  # or change_params missing

    change_params = pickle.loads(passwd_events[-1]['change_params'])

    assert isinstance(change_params, dict)  # bad change_params value
    assert 'password' in change_params  # missing password param

    stored_password = change_params['password']

    if hasattr(cereconf, 'PASSWORD_GPG_RECIPIENT_ID'):
        # tests when encryption should be performed
        assert stored_password.startswith('GPG:')
        # test decryption
        assert (
            gpgme_decrypt(
                base64.b64decode(stored_password[4:])
            ) == password_str)
    else:
        # tests when no encryption is performed
        assert password_str in stored_password


@pytest.mark.skip(reason="not done yet")
def test_move_object(user_sync, person, ad_accounts):
    """Move an AD object to another OU in AD."""
    # We target a user
    # account = accounts[0]

    # Start the fullsync
    user_sync.fetch_cerebrum_data()

    # TODO:
    # 1. Give input to simulate the response from AD:
    # 2. Assert that the MockADServer.move_object is called, and is given
    # the correct location.
    #
    # assert
