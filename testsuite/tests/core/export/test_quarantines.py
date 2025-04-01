# encoding: utf-8
"""
Unit tests for :mod:`Cerebrum.export.quarantines`.
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

from Cerebrum.export import quarantines as q_export
from Cerebrum.export import base as base_export

#
# Some quarantine codes
#


Q_FOO = "q-foo-a04f36c3"
Q_BAR = "q-bar-a04f36c4"
Q_BAZ = "q-bar-a04f36c5"

# A generic, non-existing code value (of any type)
INVALID = "missing-dea105ef"


@pytest.fixture
def q_foo(constant_module, constant_creator):
    return constant_creator(constant_module._QuarantineCode, Q_FOO)


@pytest.fixture
def q_bar(constant_module, constant_creator):
    return constant_creator(constant_module._QuarantineCode, Q_BAR)


@pytest.fixture
def q_baz(constant_module, constant_creator):
    return constant_creator(constant_module._QuarantineCode, Q_BAZ)


#
# Create three accounts with various quarantine states
#


@pytest.fixture
def today():
    return datetime.date.today()


@pytest.fixture
def account_a(account_creator, initial_account, initial_group,
              today, q_foo, q_bar, q_baz):
    """ Account with quarntines: foo, bar, baz (only bar is active). """
    account, _ = next(account_creator(initial_group, 1))
    account.add_entity_quarantine(
        qtype=q_foo,
        creator=initial_account.entity_id,
        description="past test quarantine foo",
        start=(today - datetime.timedelta(days=180)),
        end=(today - datetime.timedelta(days=30)),
    )
    account.add_entity_quarantine(
        qtype=q_bar,
        creator=initial_account.entity_id,
        description="test quarantine bar",
        start=(today - datetime.timedelta(days=30)),
    )
    account.add_entity_quarantine(
        qtype=q_baz,
        creator=initial_account.entity_id,
        description="future test quarantine baz",
        start=(today + datetime.timedelta(days=30)),
    )
    account.write_db()
    return account


@pytest.fixture
def account_b(account_creator, initial_account, initial_group,
              today, q_foo, q_bar, q_baz):
    """ Account with quarntine baz (but temporarily disabled). """
    account, _ = next(account_creator(initial_group, 1))
    account.add_entity_quarantine(
        qtype=q_baz,
        creator=initial_account.entity_id,
        description="disabled test quarantine baz",
        start=(today - datetime.timedelta(days=30)),
    )
    account.disable_entity_quarantine(
        qtype=q_baz,
        until=(today + datetime.timedelta(days=7)),
    )
    account.write_db()
    return account


@pytest.fixture
def account_c(account_creator, initial_group):
    """ An account without any quarntines. """
    account, _ = next(account_creator(initial_group, 1))
    account.exire_date = datetime.date.today() + datetime.timedelta(days=7)
    account.write_db()
    return account


#
# constant lookup helper tests
#


def test_get_quarantines_str(const, q_foo, q_bar):
    values = [Q_FOO, Q_BAR]
    expected = [q_foo, q_bar]
    results = list(q_export.get_quarantines(const, values))
    assert results == expected


def test_get_quarantines_verify(const, q_foo, q_bar):
    expected = [q_foo, q_bar]
    results = list(q_export.get_quarantines(const, expected))
    assert results == expected


def test_get_quarantines_invalid(const, q_foo):
    values = [Q_FOO, Q_BAR]  # Q_BAR doesn't exist
    with pytest.raises(LookupError) as exc_info:
        list(q_export.get_quarantines(const, values))
    error_msg = six.text_type(exc_info.value)
    assert Q_BAR in error_msg


def test_get_entity_types_str(const, q_foo, q_bar):
    expected = [const.entity_person, const.entity_account]
    values = [six.text_type(c) for c in expected]
    results = list(q_export.get_entity_types(const, values))
    assert results == expected


def test_get_entity_types_verify(const):
    expected = [const.entity_person, const.entity_account]
    results = list(q_export.get_entity_types(const, expected))
    assert results == expected


def test_get_entity_types_invalid(const):
    values = [six.text_type(const.entity_account), INVALID]
    with pytest.raises(LookupError) as exc_info:
        list(q_export.get_entity_types(const, values))
    error_msg = six.text_type(exc_info.value)
    assert INVALID in error_msg


#
# quarantine fetcher bad init tests
#

def test_init_fetcher_bad_quarantine(database):
    with pytest.raises(ValueError) as exc_info:
        q_export._QuarantineFetcher(database, (INVALID,), None, True)
    error_msg = six.text_type(exc_info.value)
    assert error_msg.startswith("Invalid quarantine type")
    assert INVALID in error_msg


def test_init_fetcher_empty_quarantine(database):
    with pytest.raises(ValueError) as exc_info:
        q_export._QuarantineFetcher(database, (), None, True)
    error_msg = six.text_type(exc_info.value)
    assert error_msg == "No quarantine types given"


def test_init_fetcher_duplicate_quarantine(database, q_foo):
    with pytest.raises(ValueError) as exc_info:
        q_export._QuarantineFetcher(database, (q_foo, q_foo), None, True)
    error_msg = six.text_type(exc_info.value)
    assert error_msg.startswith("Duplicate quarantine type")
    assert Q_FOO in error_msg


#
# quarantine fetcher tests
#


@pytest.fixture
def q_fetcher(database, const, q_foo, q_bar, q_baz):
    entity_types = (const.entity_account,)
    quarantines = (q_foo, q_bar, q_baz)
    return q_export._QuarantineFetcher(database,
                                       quarantines,
                                       entity_types,
                                       only_active=True)


def test_fetch_all_active(q_fetcher, account_a, account_b, account_c):
    results = q_fetcher.get_all()
    assert len(results) == 1
    assert len(results[account_a.entity_id]) == 1


def test_fetch_all(q_fetcher, account_a, account_b, account_c):
    q_fetcher.only_active = False
    results = q_fetcher.get_all()
    assert len(results) == 2
    assert len(results[account_a.entity_id]) == 3
    assert len(results[account_b.entity_id]) == 1


def test_fetch_one_active(q_fetcher, account_a, account_b, account_c,
                          today, q_bar):
    result = q_fetcher.get_one(account_a.entity_id)
    assert set(result) == set((q_bar,))
    # Verify data structure
    q_data = result[q_bar]
    assert q_data['entity_id'] == account_a.entity_id
    assert q_data['quarantine_type'] == q_bar
    assert q_data['quarantine_type'] == q_bar
    assert q_data['disable_until'] is None
    assert q_data['start_date'] < today
    assert q_data['end_date'] is None
    assert q_data['description']


def test_fetch_one_missing_active(q_fetcher, account_a, account_b, account_c):
    assert q_fetcher.get_one(account_b.entity_id) is base_export.MISSING
    assert q_fetcher.get_one(account_c.entity_id) is base_export.MISSING


def test_fetch_no_filter(database, account_a, account_b, account_c):
    fetcher = q_export._QuarantineFetcher(database, quarantines=None,
                                          entity_types=None, only_active=False)

    assert len(fetcher.get_one(account_a.entity_id)) == 3
    assert len(fetcher.get_one(account_b.entity_id)) == 1
    assert fetcher.get_one(account_c.entity_id) is base_export.MISSING


#
# quarantine cache tests
#


@pytest.fixture
def q_cache(database, const, q_foo, q_bar, q_baz):
    entity_types = (const.entity_account,)
    quarantines = (q_foo, q_bar, q_baz)
    return q_export.QuarantineCache(database, quarantines, entity_types,
                                    only_active=True)


def test_cache_get(q_cache, account_a, account_b, q_bar):
    result = q_cache.get(account_a.entity_id)
    assert len(result) == 1
    assert q_bar in result
    assert q_cache.get(account_b.entity_id) is None


def test_cache_get_again(q_cache, account_a, account_b):
    result = q_cache.get(account_a.entity_id)
    assert len(result) == 1
    # test cached result for account-a is the same
    assert q_cache.get(account_a.entity_id) == result

    q_cache.get(account_b.entity_id) is None
    # test cached result for acocunt-b
    assert q_cache.get(account_b.entity_id) is None


def test_cache_get_cached(q_cache, account_a, account_b):
    q_cache.update_all()

    result = q_cache.get(account_a.entity_id)
    assert len(result) == 1

    assert q_cache.get(account_b.entity_id) is None
