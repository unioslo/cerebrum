# encoding: utf-8
"""
Unit tests for :mod:`Cerebrum.export.base`.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest
# import six

from Cerebrum.export import base


#
# EntityFetcher test
#


class MockFetcher(base.EntityFetcher):

    mock_data = {
        1: {
            "foo": 101,
            "bar": 102,
        },
        2: {
            "foo": 201,
        },
        3: {
            "bar": 302,
            "baz": 303,
        },
    }

    def get_one(self, entity_id):
        if entity_id in self.mock_data:
            return dict(self.mock_data[entity_id])
        return base.MISSING

    def get_all(self):
        return {k: dict(d) for k, d in self.mock_data.items()}


def test_abstract_fetcher_one():
    f = base.EntityFetcher()
    with pytest.raises(NotImplementedError):
        f.get_one(1)


def test_abstract_fetcher_all():
    f = base.EntityFetcher()
    with pytest.raises(NotImplementedError):
        f.get_all()


def test_example_fetcher_one():
    result = MockFetcher().get_one(1)
    assert result == MockFetcher.mock_data[1]


def test_example_fetcher_one_missing():
    result = MockFetcher().get_one(-3)
    assert result is base.MISSING


def test_example_fetcher_all():
    result = MockFetcher().get_all()
    assert result == MockFetcher.mock_data


#
# EntityCache test
#


@pytest.fixture
def cache():
    fetcher = MockFetcher()
    return base.EntityCache(fetcher)


def test_cache_init(cache):
    assert cache.fetcher
    assert not cache.found
    assert not cache.missing
    assert not cache.cached_all


def test_update_all(cache):
    cache.update_all()
    assert not cache.missing
    assert cache.cached_all
    assert cache.found == MockFetcher.mock_data


def test_update_one_hit(cache):
    cache.update_one(1)
    assert not cache.missing
    assert not cache.cached_all
    assert cache.found
    assert cache.found[1] == MockFetcher.mock_data[1]


def test_update_one_miss(cache):
    missing_id = -3
    cache.update_one(missing_id)
    assert cache.missing
    assert missing_id not in cache.found
    assert missing_id in cache.missing
    assert not cache.cached_all


def test_reupdate_one_hit(cache):
    cache.update_one(1)
    cache.update_one(1)
    assert not cache.missing
    assert not cache.cached_all
    assert cache.found
    assert cache.found[1] == MockFetcher.mock_data[1]


def test_reupdate_one_miss(cache):
    missing_id = -3
    cache.update_one(missing_id)
    cache.update_one(missing_id)
    assert cache.missing
    assert missing_id not in cache.found
    assert missing_id in cache.missing
    assert not cache.cached_all


def test_cached_getitem_hit(cache):
    cache.update_all()

    example_id = 1
    result = cache[example_id]

    assert cache.cached_all
    assert cache.found[example_id] == MockFetcher.mock_data[example_id]
    assert result == MockFetcher.mock_data[example_id]


def test_cached_getitem_miss(cache):
    cache.update_all()
    with pytest.raises(KeyError):
        cache[-3]


def test_uncached_getitem_hit(cache):
    example_id = 1
    result = cache[example_id]

    assert example_id not in cache.missing
    assert example_id in cache.found
    assert result == MockFetcher.mock_data[example_id]


def test_uncached_getitem_miss(cache):
    missing_id = -3

    with pytest.raises(KeyError):
        cache[missing_id]

    assert missing_id in cache.missing
    assert missing_id not in cache.found


DEFAULT = object()


def test_cached_get_hit(cache):
    cache.update_all()
    example_id = 1
    result = cache.get(example_id, default=DEFAULT)
    assert result == MockFetcher.mock_data[example_id]


def test_cached_get_miss(cache):
    cache.update_all()
    result = cache.get(-3, default=DEFAULT)
    assert result is DEFAULT


def test_uncached_get_hit(cache):
    example_id = 1
    result = cache.get(example_id, default=DEFAULT)
    assert result == MockFetcher.mock_data[example_id]


def test_uncached_get_miss(cache):
    result = cache.get(-3, default=DEFAULT)
    assert result is DEFAULT
