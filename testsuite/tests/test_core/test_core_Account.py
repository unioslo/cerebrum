# -*- coding: utf-8 -*-
""" Basic tests for Cerebrum/Account.py.

Searching (members and groups) has to be thoroughly tested.
"""
from __future__ import unicode_literals

import logging
import os
import pytest
import sys

from Cerebrum import Errors
from datasource import BasicAccountSource, BasicPersonSource
from datasource import expired_filter, nonexpired_filter

logger = logging.getLogger(__name__)

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


class LegacyTestAccount(object):
    def __init__(self, *args):
        global DatabaseTools
        from dbtools import DatabaseTools


DatabaseTools = None


@pytest.fixture
def cereconf():
    u""" 'cereconf' config.

    This fixture allows test modules to change cereconf settings when certain
    settings need to be tested, or when certain changes needs to be injected in
    the config.
    """
    # from pprint import pprint
    # pprint(sys.modules)
    try:
        import Cerebrum.default_config
        CEREBRUM_DATABASE_NAME = os.environ.get('CEREBRUM_DATABASE_NAME', None)
        DB_AUTH_DIR = os.environ.get('DB_AUTH_DIR', None)
        if not CEREBRUM_DATABASE_NAME or not DB_AUTH_DIR:
            raise KeyError("Missing environment variables")
        CEREBRUM_DATABASE_CONNECT_DATA = {
            u'client_encoding': u'UTF-8',
            u'host': 'dbpg-cere-utv.uio.no',
            u'table_owner': 'cerebrum',
            u'user': 'cerebrum',
        }
        CLASS_ACCOUNT = (
            u'Cerebrum.modules.no.uio.Account/AccountUiOMixin',
            u'Cerebrum.modules.apikeys.mixins/ApiMappingAccountMixin',
        )
        CLASS_CL_CONSTANTS = (
            u'Cerebrum.modules.apikeys.constants/CLConstants',
            u'Cerebrum.modules.hostpolicy.HostPolicyConstants/CLConstants',
            u'Cerebrum.modules.EntityTraitConstants/CLConstants',
            u'Cerebrum.modules.exchange.CLConstants/CLConstants',
            u'Cerebrum.Constants/CLConstants',
        )

        CLASS_CONSTANTS = (
            u'Cerebrum.modules.no.Constants/ConstantsCommon',
            u'Cerebrum.modules.no.uio.Constants/Constants',
        )
        CLASS_ENTITY = (
            u'Cerebrum.modules.EntityTrait/EntityTrait',
            u'Cerebrum.modules.bofhd.bofhd_mixins/BofhdAuthEntityMixin',
        )
        CLASS_POSIX_GROUP = (
            u'Cerebrum.modules.no.uio.PosixGroup/PosixGroupUiOMixin',
            u'Cerebrum.modules.PosixGroup/PosixGroup',
        )
        CLASS_POSIX_USER = (
            u'Cerebrum.modules.no.uio.PosixUser/PosixUserUiOMixin',
            u'Cerebrum.modules.PosixUser/PosixUser',
        )
        CLASS_GROUP = (
            u'Cerebrum.modules.no.uio.Group/GroupUiOMixin',
            u'Cerebrum.modules.posix.mixins/PosixGroupMixin',
            u'Cerebrum.Group/Group',
        )
        Cerebrum.default_config.CEREBRUM_DATABASE_CONNECT_DATA = CEREBRUM_DATABASE_CONNECT_DATA
        Cerebrum.default_config.CEREBRUM_DATABASE_NAME = CEREBRUM_DATABASE_NAME
        Cerebrum.default_config.DB_AUTH_DIR = DB_AUTH_DIR
        Cerebrum.default_config.CLASS_CONSTANTS = CLASS_CONSTANTS
        Cerebrum.default_config.CLASS_ACCOUNT = CLASS_ACCOUNT
        Cerebrum.default_config.CLASS_GROUP = CLASS_GROUP
        Cerebrum.default_config.CLASS_POSIX_GROUP = CLASS_POSIX_GROUP
        Cerebrum.default_config.CLASS_POSIX_USER = CLASS_POSIX_USER
        Cerebrum.default_config.CLASS_CL_CONSTANTS = CLASS_CL_CONSTANTS
        Cerebrum.default_config.CLASS_ENTITY = CLASS_ENTITY
        sys.modules["cereconf"] = Cerebrum.default_config
        return sys.modules["cereconf"]
    except ImportError:
        pytest.xfail(u"Unable to import 'cereconf'")


@pytest.fixture
def factory(cereconf):
    u""" `Cerebrum.Utils.Factory`.

    We list cereconf as a 'dependency' in order to have it processed before
    importing and using the factory.
    """
    global Factory
    logger.debug(cereconf)
    from Cerebrum.Utils import Factory
    return Factory


@pytest.fixture()
def database(factory):

    legacy = LegacyTestAccount()

    legacy._db = factory.get('Database')()
    legacy._db.cl_init(change_program='nosetests')
    legacy._db.commit = legacy._db.rollback  # Let's try not to screw up the db

    legacy._ac = factory.get('Account')(legacy._db)
    legacy._co = factory.get('Constants')(legacy._db)

    # Data sources
    legacy.account_ds = BasicAccountSource()
    legacy.person_ds = BasicPersonSource()

    # Tools for creating and destroying temporary db items
    legacy.db_tools = DatabaseTools(legacy._db)
    legacy.db_tools._ac = legacy._ac

    yield legacy

    legacy.db_tools.clear_groups()
    legacy.db_tools.clear_accounts()
    legacy.db_tools.clear_persons()
    legacy.db_tools.clear_constants()
    legacy._db.rollback()


@pytest.fixture
def accounts(database):
    u""" `Cerebrum.Utils.Factory`.

    We list cereconf as a 'dependency' in order to have it processed before
    importing and using the factory.
    """
    database._accounts = []
    for account in database.account_ds(limit=5):
        entity_id = database.db_tools.create_account(account)
        account['entity_id'] = entity_id
        database._accounts.append(account)
    return database


def test_account_populate(database):
    """ Account.populate() with basic info. """
    logger.debug(database)
    logger.debug(dir(database))
    logger.debug(type(database))
    creator_id = database.db_tools.get_initial_account_id()
    owner_id = database.db_tools.get_initial_group_id()
    account = database.account_ds.get_next_item()

    database._ac.clear()
    database._ac.populate(account['account_name'], database._co.entity_group,
                      owner_id, database._co.account_program, creator_id, None)
    database._ac.write_db()
    assert hasattr(database._ac, 'entity_id') is True

    entity_id = database._ac.entity_id
    database._ac.clear()
    database._ac.find(entity_id)
    assert database._ac.account_name == account['account_name']

    # If the test fails, there's nothing to clean up.
    # If it succeeds, we can delete the account
    database.db_tools.delete_account_id(entity_id)


def test_account_create(database):
    """ Account.create() with a new person. """
    creator_id = database.db_tools.get_initial_account_id()
    owner_id = database.db_tools.create_person(
        database.person_ds.get_next_item())

    account = database.account_ds.get_next_item()
    database._ac.clear()
    database._ac.populate(account['account_name'], database._co.entity_person,
                      owner_id, None, creator_id, None)
    database._ac.write_db()

    assert hasattr(database._ac, 'entity_id') is True

    entity_id = database._ac.entity_id
    database._ac.clear()
    database._ac.find(entity_id)

    assert database._ac.account_name == account['account_name']
    database.db_tools.delete_account_id(entity_id)


def test_simple_find(accounts):
    """ Account.find() accounts. """
    # Fails if we get a Cerebrum.NotFoundException
    assert len(accounts._accounts) >= 1  # We need at least 1 account
    count = 0
    for account in accounts._accounts:
        accounts._ac.clear()
        accounts._ac.find(account['entity_id'])
        count += 1
    assert len(accounts._accounts) == count


def test_simple_find_fail(accounts):
    """ Account.find() non-existing account. """
    accounts._ac.clear()

    # negative IDs are impossible in Cerebrum, should raise notfound-error
    with pytest.raises(Errors.NotFoundError):
        assert accounts._ac.find(-10)


def test_find_by_name(accounts):
    """ Account.find_by_name() accounts. """
    assert len(accounts._accounts) >= 1  # We need at least 1 account
    count = 0
    for account in accounts._accounts:
        accounts._ac.clear()
        accounts._ac.find_by_name(account['account_name'])
        count += 1
    assert len(accounts._accounts) == count


def test_find_by_name_fail(accounts):
    """ Account.find_by_name() non-existing account. """
    accounts._ac.clear()

    # entity_name is a varchar(256), no group with longer name should exist
    with pytest.raises(Errors.NotFoundError):
        assert accounts._ac.find_by_name('n' * (256 + 1))


def test_is_expired(accounts):
    """ Account.is_expired() for expired and non-expired accounts. """
    non_expired = _set_of_ids(filter(nonexpired_filter, accounts._accounts))

    # We must have at least one expired and one non-expired account
    assert (len(non_expired) > 0 and
            len(non_expired) < len(_set_of_ids(accounts._accounts)))

    for account in accounts._accounts:
        accounts._ac.clear()
        accounts._ac.find(account['entity_id'])
        if int(accounts._ac.entity_id) in non_expired:
            assert accounts._ac.is_expired() is False
        else:
            assert accounts._ac.is_expired() is True


def test_search_owner(accounts):
    """ Account.search() with owner_id argument. """
    created_ids = _set_of_ids(accounts._accounts)
    owner_id = accounts.db_tools.get_initial_group_id()

    assert len(created_ids) >= 1

    results = accounts._ac.search(owner_id=owner_id, expire_start=None)
    owned_by = _set_of_ids(map(lambda x: dict(x), results))

    # INITIAL_GROUPNAME could own more than what we've created, but all our
    # created groups should be returned by the search
    assert owned_by.issuperset(created_ids) is True
    assert owned_by.issuperset(created_ids) is True

    # We should not get any results with another owner_id
    for result in results:
        group_id = accounts.db_tools.get_initial_group_id()
        assert int(result['owner_id']) == group_id


def test_search_owner_sequence(accounts):
    """ Account.search() with sequence owner_id argument. """
    created_ids = _set_of_ids(accounts._accounts)
    assert len(created_ids) == 5

    # Creator of our default accounts
    group_id = accounts.db_tools.get_initial_group_id()

    # Create a person, so that we can create a personal acocunt
    person_id = accounts.db_tools.create_person(
        accounts.person_ds.get_next_item())

    # Create a personal account, and add to our created_ids
    account = accounts.account_ds.get_next_item()
    account_id = accounts.db_tools.create_account(
        account, person_owner_id=person_id)

    created_ids.add(account_id)

    for seq_type in (set, list, tuple):
        sequence = seq_type((person_id, group_id))
        results = list(accounts._ac.search(owner_id=sequence,
                                       expire_start=None))
        owned_by_seq = _set_of_ids(map(lambda x: dict(x), results))
        assert len(results) >= len(created_ids) + 1
        assert owned_by_seq.issuperset(created_ids) is True
        for result in results:
            assert int(result['owner_id']) in sequence


def test_search_filter_expired(accounts):
    """ Account.search() with expire_start, expire_stop args. """
    all_accounts = _set_of_ids(accounts._accounts)
    non_expired = _set_of_ids(filter(nonexpired_filter, accounts._accounts))
    expired = _set_of_ids(filter(expired_filter, accounts._accounts))

    # Test criterias
    assert len(non_expired) >= 1
    assert len(expired) >= 1

    search_params = (({'expire_start': None, 'expire_stop': None,
          'owner_id': accounts.db_tools.get_initial_group_id()},
         all_accounts, set()),
        ({'expire_start': '[:now]', 'expire_stop': None,
          'owner_id': accounts.db_tools.get_initial_group_id()},
         non_expired, expired),
        ({'expire_start': None, 'expire_stop': '[:now]',
          'owner_id': accounts.db_tools.get_initial_group_id()},
         expired, non_expired),)

    # Tests: search params, must match
    for params, match_set, fail_set in search_params:
        result = _set_of_ids(
            map(lambda x: dict(x), accounts._ac.search(**params)))
        assert len(result) >= len(match_set)
        assert result.issuperset(match_set) is True
        assert result.intersection(fail_set) == set()


def test_search_name(accounts):
    """ Account.search() for name. """
    tests = [({'expire_start': None, 'name': a['account_name']},
              int(a['entity_id'])) for a in accounts._accounts]

    assert len(tests) >= 1  # We need at least 1 group for this test
    for params, match_id in tests:
        result = accounts._ac.search(**params)
        assert len(result) == 1
        assert int(result[0]['account_id']) == match_id


def test_search_name_wildcard(accounts):
    """ Account.search() for name with wildcards. """
    search_expr = accounts.account_ds.name_prefix + '%'
    result = list(map(lambda x: dict(x),
            accounts._ac.search(name=search_expr, expire_start=None)))
    assert len(result) == len(accounts._accounts)

    # The test group should contain names with unique prefixes, or this
    # test will fail...
    assert _set_of_ids(result) == _set_of_ids(accounts._accounts)


def test_equality(accounts):
    """ Account __eq__ comparison. """
    assert len(accounts._accounts) >= 2
    ac1 = Factory.get('Account')(accounts._db)
    ac1.find_by_name(accounts._accounts[0]['account_name'])
    ac2 = Factory.get('Account')(accounts._db)
    ac2.find_by_name(accounts._accounts[1]['account_name'])
    ac3 = Factory.get('Account')(accounts._db)
    ac3.find_by_name(accounts._accounts[0]['account_name'])
    assert ac1 == ac3
    assert ac1 != ac2
    assert ac2 != ac3


def test_set_password(accounts):
    """ Account.set_password(). """
    assert len(accounts._accounts) >= 2

    for account in accounts._accounts:
        password = account.get('password', 'default_password')
        accounts._ac.clear()
        accounts._ac.find_by_name(account['account_name'])
        accounts._ac.set_password(password)
        accounts._ac.write_db()
        accounts._ac.clear()
        accounts._ac.find_by_name(account['account_name'])
        assert accounts._ac.verify_auth(password) is True


def test_verify_password(accounts):
    has_passwd = [a for a in accounts._accounts if a.get('password')]
    assert len(has_passwd) > 1

    # Password should have been set when created
    for account in has_passwd:
        accounts._ac.clear()
        accounts._ac.find_by_name(account['account_name'])
        assert accounts._ac.verify_auth(account['password']) is True
        assert accounts._ac.verify_auth(account['password'] + 'x') == []


def test_encrypt_verify_methods(accounts):
    """ Account encrypt_password and verify_password methods. """

    salt = u'somes4lt'
    password = u'ex-mpLe-p4~~'

    must_encode = ['auth_type_md5_crypt',
                   'auth_type_sha256_crypt', 'auth_type_sha512_crypt',
                   'auth_type_ssha', 'auth_type_md4_nt',
                   'auth_type_plaintext', 'auth_type_md5_unsalt']

    # For some reason, md4_unsalt does not verify
    must_verify = ['auth_type_md5_crypt',
                   'auth_type_sha256_crypt', 'auth_type_sha512_crypt',
                   'auth_type_ssha', 'auth_type_md4_nt',
                   'auth_type_plaintext']

    auth_type_consts = [d for d in dir(accounts._co) if
                        d.startswith('auth_type_')]

    assert set(must_encode).issubset(set(auth_type_consts)) is True
    assert set(must_verify).issubset(set(auth_type_consts)) is True

    verify_password = accounts._ac.verify_password  # Alias long name
    for m in auth_type_consts:
        method = getattr(accounts._co, m)
        try:
            # We add the salt to the password, just to get a different
            # password from the unsalted test
            mix = salt + password
            salted = accounts._ac.encrypt_password(method, mix, salt)
            assert bool(salted) is True
            unsalted = accounts._ac.encrypt_password(method, password)
            assert bool(unsalted) is True
        except Errors.NotImplementedAuthTypeError:
            assert method not in must_encode
            continue
        try:
            assert verify_password(method, salt + password, salted) is True
            assert verify_password(method, password, salted) is False
            assert verify_password(method, password, unsalted) is True
            assert verify_password(method, salt + password, unsalted) is False
        except ValueError:
            assert method not in must_verify


def test_populate_affect_auth(accounts):
    """ Account.populate_auth_type() and Account.affect_auth_types. """
    # populate_auth_type and affect_auth_types will always be used in
    # conjunction, and is not possible to test independently without
    # digging into the Account class implementation.
    #
    assert len(accounts._accounts) >= 1

    # Tuples of (auth_method, cryptstring, try_to_affect)
    tests = [(accounts._co.auth_type_sha256_crypt, 'crypt-resgcsgq', False),
             (accounts._co.auth_type_sha512_crypt, 'crypt-juoxpixs', True)]
    # This should change the sha-512 crypt, but not the sha-256 crypt:

    for account in accounts._accounts:
        accounts._ac.clear()
        accounts._ac.find_by_name(account['account_name'])

        # Populate each of the auth methods given in tests
        for method, crypt, _ in tests:
            accounts._ac.populate_authentication_type(method, crypt)

        # Only affect selected auth methods
        accounts._ac.affect_auth_types(
            *(method for method, _, affect in tests if affect))
        accounts._ac.write_db()
        accounts._ac.clear()
        accounts._ac.find_by_name(account['account_name'])

        # Check that only affected auth method crypts were altered
        for method, new_crypt, affect in tests:
            try:
                # We add the salt to the password, just to get a different
                # password from the unsalted test
                salted = self._ac.encrypt_password(
                    method, salt + password, salt)
                self.assertTrue(bool(salted))
                unsalted = self._ac.encrypt_password(method, password)
                self.assertTrue(bool(unsalted))
            except Errors.NotImplementedAuthTypeError:
                self.assertNotIn(method, must_encode)
                continue
            try:
                self.assertTrue(self._ac.verify_password(
                    method, salt + password, salted))
                self.assertFalse(self._ac.verify_password(
                    method, password, salted))
                self.assertTrue(self._ac.verify_password(
                    method, password, unsalted))
                self.assertFalse(self._ac.verify_password(
                    method, salt + password, unsalted))
            except Errors.NotImplementedAuthTypeError:
                self.assertNotIn(method, must_verify)
            # except ValueError:
                # self.assertNotIn(method, must_verify)
