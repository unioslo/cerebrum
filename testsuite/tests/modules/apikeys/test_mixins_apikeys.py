# encoding: utf-8
""" Tests for mod:`Cerebrum.modules.apikeys.dbal` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

from Cerebrum import Errors
from Cerebrum.modules.apikeys import dbal
from Cerebrum.modules.apikeys import mixins


@pytest.fixture
def group(group_creator):
    group, _ = next(group_creator(1))
    return group


@pytest.fixture
def account_cls(account_cls):
    return mixins.ApiMappingAccountMixin


@pytest.fixture
def account(account_creator, group):
    account, _ = next(account_creator(group, 1))
    return account


@pytest.fixture
def apikeys(database):
    return dbal.ApiMapping(database)


IDENTIFIER_1 = "sub-1-cafde8bbf7444ebb"
IDENTIFIER_2 = "sub-2-6196db0c0affcbfc"
IDENTIFIER_3 = "sub-3-fda3cba6215b5f08"


@pytest.fixture
def accounts(account_creator, apikeys, group):
    ac_1, ac_2 = [a for a, _ in account_creator(group, 2)]
    apikeys.set(IDENTIFIER_1, ac_1.entity_id)
    apikeys.set(IDENTIFIER_2, ac_1.entity_id)
    apikeys.set(IDENTIFIER_3, ac_2.entity_id)
    return [ac_1, ac_2]


def test_account_delete_without_keys(account):
    entity_id = account.entity_id
    account.delete()
    account.clear()
    with pytest.raises(Errors.NotFoundError):
        account.find(entity_id)


def test_account_delete(apikeys, accounts):
    account_1, account_2 = accounts
    account_1.delete()

    # Check that the api keys for the deleted account are gone
    assert not apikeys.exists(IDENTIFIER_1)
    assert not apikeys.exists(IDENTIFIER_2)

    # Check that other api keys remain
    assert apikeys.exists(IDENTIFIER_3)
