# encoding: utf-8
""" Tests for mod:`Cerebrum.modules.apikeys.dbal` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest
import six

from Cerebrum.modules.apikeys import dbal


@pytest.fixture
def group(group_creator):
    group, _ = next(group_creator(1))
    return group


@pytest.fixture
def account(account_creator, group):
    account, _ = next(account_creator(group, 1))
    return account


@pytest.fixture
def account_2(account_creator, group):
    account, _ = next(account_creator(group, 1))
    return account


@pytest.fixture
def apikeys(database):
    return dbal.ApiMapping(database)


IDENTIFIER_1 = "sub-1-cafde8bbf7444ebb"
IDENTIFIER_2 = "sub-2-6196db0c0affcbfc"


def test_get(apikeys, account):
    apikeys.set(IDENTIFIER_1, account.entity_id)
    apikeys.set(IDENTIFIER_2, account.entity_id)
    row = apikeys.get(IDENTIFIER_1)
    assert row['identifier'] == IDENTIFIER_1
    assert row['account_id'] == account.entity_id
    assert row['description'] is None
    assert row['updated_at']


def test_get_no_identifier(apikeys):
    with pytest.raises(ValueError, match="missing identifier"):
        apikeys.get("")


def test_exists_miss(apikeys):
    assert not apikeys.exists(IDENTIFIER_1)


def test_exists_hit(apikeys, account):
    apikeys.set(IDENTIFIER_1, account.entity_id)
    assert apikeys.exists(IDENTIFIER_1)


def test_exists_no_identifier(apikeys, account):
    with pytest.raises(ValueError, match="missing identifier"):
        apikeys.exists("")


def test_insert(apikeys, account):
    row = apikeys.set(IDENTIFIER_1, account.entity_id)
    assert apikeys.exists(IDENTIFIER_1)
    assert row['identifier'] == IDENTIFIER_1
    assert row['account_id'] == account.entity_id


def test_update(apikeys, account):
    apikeys.set(IDENTIFIER_1, account.entity_id)
    updated = apikeys.set(IDENTIFIER_1, account.entity_id, description="test")
    row = apikeys.get(IDENTIFIER_1)
    assert dict(updated) == dict(row)


def test_update_noop(apikeys, account):
    apikeys.set(IDENTIFIER_1, account.entity_id)
    updated = apikeys.set(IDENTIFIER_1, account.entity_id)
    row = apikeys.get(IDENTIFIER_1)
    assert dict(updated) == dict(row)


def test_update_new_account(apikeys, account, account_2):
    apikeys.set(IDENTIFIER_1, account.entity_id)
    with pytest.raises(ValueError) as exc_info:
        apikeys.set(IDENTIFIER_1, account_2.entity_id)

    error_msg = six.text_type(exc_info.value)
    assert "already assigned to" in error_msg


def test_delete(apikeys, account):
    apikeys.set(IDENTIFIER_1, account.entity_id)
    apikeys.set(IDENTIFIER_2, account.entity_id)
    row = apikeys.delete(IDENTIFIER_1)
    assert apikeys.exists(IDENTIFIER_2)
    assert not apikeys.exists(IDENTIFIER_1)
    assert row['identifier'] == IDENTIFIER_1
    assert row['account_id'] == account.entity_id


def test_search_account(apikeys, account, account_2):
    to_find = dict(apikeys.set(IDENTIFIER_1, account.entity_id))
    apikeys.set(IDENTIFIER_2, account_2.entity_id)
    results = list(apikeys.search(account_id=account.entity_id))
    assert len(results) == 1
    assert dict(results[0]) == to_find


def test_search_identifier(apikeys, account, account_2):
    to_find = dict(apikeys.set(IDENTIFIER_1, account.entity_id))
    apikeys.set(IDENTIFIER_2, account_2.entity_id)
    results = list(apikeys.search(identifier=IDENTIFIER_1))
    assert len(results) == 1
    assert dict(results[0]) == to_find


def test_search_description(apikeys, account, account_2):
    desc_1 = "test-description-" + IDENTIFIER_1
    desc_2 = "test-description-" + IDENTIFIER_2
    to_find = dict(apikeys.set(IDENTIFIER_1, account.entity_id,
                               description=desc_1))
    apikeys.set(IDENTIFIER_2, account_2.entity_id, description=desc_2)
    results = list(apikeys.search(description=desc_1))
    assert len(results) == 1
    assert dict(results[0]) == to_find


def test_search_description_pattern(apikeys, account, account_2):
    desc_1 = "test-description-" + IDENTIFIER_1
    desc_2 = "Test-Description-" + IDENTIFIER_2
    to_find = dict(apikeys.set(IDENTIFIER_1, account.entity_id,
                               description=desc_1))
    apikeys.set(IDENTIFIER_2, account_2.entity_id, description=desc_2)
    results = list(
        apikeys.search(
            account_id=(account.entity_id, account_2.entity_id),
            description_like="test-description-*",
        )
    )
    assert len(results) == 1
    assert dict(results[0]) == to_find


def test_search_description_empty(apikeys, account, account_2):
    desc_1 = "test-description-" + IDENTIFIER_1
    desc_2 = None
    apikeys.set(IDENTIFIER_1, account.entity_id, description=desc_1)
    to_find = dict(apikeys.set(IDENTIFIER_2, account_2.entity_id,
                               description=desc_2))
    results = list(
        apikeys.search(
            account_id=(account.entity_id, account_2.entity_id),
            description=None,
        )
    )
    assert len(results) == 1
    assert dict(results[0]) == to_find
