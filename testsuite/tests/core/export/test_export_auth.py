# encoding: utf-8
"""
Unit tests for :mod:`Cerebrum.export.auth`.
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
from Cerebrum.testutils import datasource
from Cerebrum import auth as _auth_module
from Cerebrum.export import auth as auth_export


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


def test_get_auth_types_str(const, auth_foo, auth_bar):
    values = [AUTH_FOO, AUTH_BAR]
    expected = [auth_foo, auth_bar]
    results = list(auth_export.get_auth_types(const, values))
    assert results == expected


def test_get_auth_types_verify(const, auth_foo, auth_bar):
    expected = [auth_foo, auth_bar]
    results = list(auth_export.get_auth_types(const, expected))
    assert results == expected


def test_get_auth_types_invalid(const, auth_foo):
    values = [AUTH_FOO, AUTH_BAR]  # no auth_bar
    with pytest.raises(LookupError) as exc_info:
        list(auth_export.get_auth_types(const, values))
    error_msg = six.text_type(exc_info.value)
    assert AUTH_BAR in error_msg


@pytest.fixture
def auth_fetcher(database, auth_foo, auth_bar):
    return auth_export._AuthFetcher(database, (auth_foo, auth_bar))


def test_fetch_all_filter_expired(auth_fetcher, account_a, account_b):
    # Note: this can be a bit slow (a few seconds) on large databases
    results = auth_fetcher.get_all()
    assert len(results) == 1
    assert account_a.entity_id in results
    assert account_b.entity_id not in results


def test_fetch_all_no_filter_expired(auth_fetcher, account_a, account_b):
    # Note: this can be a bit slow (a few seconds) on large databases
    auth_fetcher.filter_expired = False
    results = auth_fetcher.get_all()
    assert len(results) == 2
    assert account_a.entity_id in results
    assert account_b.entity_id in results


def test_fetch_one(auth_fetcher, account_a, account_b, auth_foo, auth_bar):
    result = auth_fetcher.get_one(account_a.entity_id)
    assert result == {
        auth_foo: "account-a",
        auth_bar: "account-a",
    }


def test_selector(auth_foo, auth_bar):
    selector = auth_export._AuthSelector([auth_bar, auth_foo])
    values = [(auth_foo, "foo"), (auth_bar, "bar")]
    expected = [(auth_bar, "bar"), (auth_foo, "foo")]
    assert list(selector(values)) == expected


def test_cache(database, auth_foo, auth_bar, account_a, account_b):
    cache = auth_export.AuthCache(database, [auth_bar, auth_foo])

    result = cache.get_authentication(account_a.entity_id)
    assert len(result) == 2
    assert result[0] == auth_bar
    assert result[1] == "account-a"


def test_get_format_mapping(const, auth_foo, auth_bar):
    input_pairs = [
        (AUTH_FOO, "foo: ${value}"),
        (AUTH_BAR, "bar-$value-baz"),
    ]
    foo, bar = auth_export.get_format_mapping(const, input_pairs)

    assert foo[0] == auth_foo
    assert foo[1].substitute(value="example") == "foo: example"
    assert bar[0] == auth_bar
    assert bar[1].substitute(value="example") == "bar-example-baz"


def test_formatter(const, auth_foo, auth_bar):
    input_pairs = [
        (AUTH_FOO, "foo: ${value}"),
        (AUTH_BAR, "bar-$value-baz"),
    ]
    formatter = auth_export.AuthFormatter(
        auth_export.get_format_mapping(const, input_pairs)
    )
    result = formatter.format(auth_bar, "secret")
    assert result == "bar-secret-baz"
