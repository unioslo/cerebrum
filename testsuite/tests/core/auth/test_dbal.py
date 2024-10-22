# encoding: utf-8
"""
Unit tests for :mod:`Cerebrum.auth.dbal`.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime

import pytest
import six

from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum.testutils import datasource
from Cerebrum import auth as _auth_module
from Cerebrum.auth import dbal


#
# Fixtures and test setup
#


@pytest.fixture
def constant_creator(constant_module):
    """ create constants that can be found with const.get_constant(). """
    attrs = []

    def create_constant(constant_type, value, *args, **kwargs):
        description = kwargs.pop('description',
                                 "test constant " + six.text_type(value))
        kwargs['description'] = description
        code = constant_type(value, *args, **kwargs)
        code.insert()

        # Inject the code as an attribute of a class that exists both in
        # in the Factory.get("Constants") and `const` fixture mro
        #
        # This is needed for some of the ConstantsBase lookup methods (e.g.
        # `get_constant`)
        attr = 'test_code_' + format(id(code), 'x')
        setattr(constant_module.CoreConstants, attr, code)
        attrs.append(attr)
        return code

    yield create_constant

    for attr in attrs:
        delattr(constant_module.CoreConstants, attr)


#
# Implement and configure two new auth methods
#


AUTH_FOO = "pw-foo-25e6a211"
AUTH_BAR = "pw-bar-a04f36c4"


@_auth_module.all_auth_methods(AUTH_FOO)
@_auth_module.all_auth_methods(AUTH_BAR)
class _MockAuthMethod(_auth_module.AuthTypePlaintext):
    pass


@pytest.fixture
def auth_foo(constant_module, constant_creator):
    return constant_creator(constant_module._AuthenticationCode, AUTH_FOO)


@pytest.fixture
def auth_bar(constant_module, constant_creator):
    return constant_creator(constant_module._AuthenticationCode, AUTH_BAR)


@pytest.fixture(autouse=True)
def _patch_cereconf(cereconf):
    cereconf.AUTH_CRYPT_METHODS = (AUTH_FOO, AUTH_BAR)


#
# Create two accounts with the given auth methods
#


@pytest.fixture
def account_cls():
    return Account.Account


@pytest.fixture
def account_creator(database, const, account_cls, initial_account,
                    auth_foo, auth_bar):
    creator_id = initial_account.entity_id
    account_ds = datasource.BasicAccountSource()

    def _create_accounts(owner, limit=1):
        owner_id = owner.entity_id
        owner_type = owner.entity_type

        for account_dict in account_ds(limit=limit):

            account = account_cls(database)
            if owner_type == const.entity_person:
                account_type = None
            else:
                account_type = const.account_program

            account.populate(
                account_dict['account_name'],
                owner_type,
                owner_id,
                account_type,
                creator_id,
                account_dict.get('expire_date'),
            )
            if account_dict.get('password'):
                account.set_password(account_dict.get('password'))
            account.write_db()
            account_dict['entity_id'] = account.entity_id
            yield account, account_dict

    return _create_accounts


@pytest.fixture
def account_a(account_creator, initial_group):
    account, _ = next(account_creator(initial_group, 1))
    account.set_password("account-a")
    account.write_db()
    return account


@pytest.fixture
def account_b(account_creator, initial_group):
    account, _ = next(account_creator(initial_group, 1))
    account.set_password("account-b")
    account.exire_date = datetime.date.today() + datetime.timedelta(days=7)
    account.write_db()
    return account


#
# Tests
#


def test_legacy_list_authentication(database, auth_foo, auth_bar,
                                    account_a, account_b):
    # Note: this can be a bit slow (a few seconds) on large databases
    results = dbal.legacy_list_authentication(
        database,
        method=(auth_foo, auth_bar),
        filter_expired=False,
    )
    assert len(results) > 2
    entity_ids = set(r['account_id'] for r in results)
    assert account_a.entity_id in entity_ids
    assert account_b.entity_id in entity_ids


def test_legacy_list_authentication_by_id(database, auth_foo, auth_bar,
                                          account_a, account_b):
    results = dbal.legacy_list_authentication(
        database,
        method=(auth_foo, auth_bar),
        account_id=(account_a.entity_id, account_b.entity_id),
        filter_expired=False,
    )
    assert len(results) == 4
    entity_ids = set(r['account_id'] for r in results)
    assert entity_ids == set((account_a.entity_id, account_b.entity_id))


def test_legacy_list_authentication_filter_expire(database, auth_foo, auth_bar,
                                                  account_a, account_b):
    results = dbal.legacy_list_authentication(
        database,
        method=(auth_foo, auth_bar),
        account_id=(account_a.entity_id, account_b.entity_id),
        filter_expired=True,
    )
    entity_ids = set(r['account_id'] for r in results)
    assert account_a.entity_id in entity_ids
    assert account_b.entity_id not in entity_ids


#
# list_authentication tests
#


def test_list_authentication(database, auth_foo, auth_bar,
                             account_a, account_b):
    results = dbal.list_authentication(
        database,
        method=(auth_foo, auth_bar),
        filter_expired=False,
    )
    assert len(results) == 4
    entity_ids = set(r['account_id'] for r in results)
    assert entity_ids == set((account_a.entity_id, account_b.entity_id))


def test_list_authentication_by_id(database, auth_foo, auth_bar,
                                   account_a, account_b):
    results = dbal.list_authentication(
        database,
        method=(auth_foo, auth_bar),
        account_id=(account_a.entity_id, account_b.entity_id),
        filter_expired=False,
    )
    assert len(results) == 4
    entity_ids = set(r['account_id'] for r in results)
    assert entity_ids == set((account_a.entity_id, account_b.entity_id))


def test_list_authentication_filter_expire(database, auth_foo, auth_bar,
                                           account_a, account_b):
    results = dbal.list_authentication(
        database,
        method=(auth_foo, auth_bar),
        account_id=(account_a.entity_id, account_b.entity_id),
        filter_expired=True,
    )
    entity_ids = set(r['account_id'] for r in results)
    assert account_a.entity_id in entity_ids
    assert account_b.entity_id not in entity_ids


#
# list_authentication_methods tests
#


def test_list_authentication_methods(database, auth_foo, auth_bar,
                                     account_a):
    results = dbal.list_authentication_methods(
        database,
    )
    assert len(results) >= 2
    methods = set(r['method'] for r in results)
    assert len(methods) == len(results)
    assert int(auth_foo) in methods
    assert int(auth_bar) in methods


def test_list_authentication_methods_by_id(database, auth_foo, auth_bar,
                                           account_a):
    results = dbal.list_authentication_methods(
        database,
        account_id=account_a.entity_id
    )
    assert len(results) == 2
    expected = sorted([int(auth_foo), int(auth_bar)])
    assert sorted([r['method'] for r in results]) == expected


#
# get_authentication tests
#


def test_get_authentication_hit(database, auth_foo, account_b):
    result = dbal.get_authentication(
        database,
        account_b.entity_id,
        auth_foo,
    )
    assert result == "account-b"


def test_get_authentication_miss(database, const, account_a):
    with pytest.raises(Errors.NotFoundError):
        dbal.get_authentication(
            database,
            account_a.entity_id,
            const.auth_type_sha512_crypt,
        )


#
# set_authentication tests
#


def test_set_authentication_insert(database, const, account_a):
    result = dbal.set_authentication(
        database,
        account_a.entity_id,
        const.auth_type_sha512_crypt,
        "secret-hash",
    )
    assert dict(result) == {
        'account_id': account_a.entity_id,
        'method': int(const.auth_type_sha512_crypt),
        'auth_data': "secret-hash",
    }
    assert [dict(result)] == [
        dict(r)
        for r in dbal.list_authentication(
            database,
            account_id=account_a.entity_id,
            method=const.auth_type_sha512_crypt,
        )
    ]


def test_set_authentication_update(database, account_a, auth_foo):
    result = dbal.set_authentication(
        database,
        account_a.entity_id,
        auth_foo,
        "secret-hash",
    )
    assert dict(result) == {
        'account_id': account_a.entity_id,
        'method': int(auth_foo),
        'auth_data': "secret-hash",
    }
    assert [dict(result)] == [
        dict(r)
        for r in dbal.list_authentication(
            database,
            account_id=account_a.entity_id,
            method=auth_foo,
        )
    ]


def test_delete_authentication(database, auth_foo, auth_bar,
                               account_a, account_b):
    results = dbal.delete_authentication(
        database,
        account_id=account_a.entity_id,
        method=auth_foo,
    )
    assert len(results) == 1
    assert results[0]['account_id'] == account_a.entity_id
    assert results[0]['method'] == int(auth_foo)

    remaining = set(
        (r['account_id'], r['method'])
        for r in dbal.list_authentication(
            database,
            method=(auth_foo, auth_bar),
            account_id=(account_a.entity_id, account_b.entity_id),
            filter_expired=False,
        )
    )
    assert remaining == set((
        (account_a.entity_id, int(auth_bar)),
        (account_b.entity_id, int(auth_foo)),
        (account_b.entity_id, int(auth_bar)),
    ))
