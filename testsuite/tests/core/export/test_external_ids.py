# encoding: utf-8
"""
Unit tests for :mod:`Cerebrum.export.external_ids`.

These tests are a bit messy, as we need to set up a lot of data fixtures.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest
import six

from Cerebrum.export import external_ids as id_export
from Cerebrum.export import base as base_export


#
# Some external id types and source systems
#


ID_TYPE_A = "id-a-c1c885f8d72"
ID_TYPE_B = "id-b-6ff43825c6c"
ID_TYPE_C = "id-c-3946f45e6ec"

SRC_FOO = "s-foo-a04f36c6"
SRC_BAR = "s-bar-a04f36c7"
SRC_BAZ = "s-baz-a04f36c8"

# A generic, non-existing code value (of any type)
INVALID = "missing-dea105ef"


@pytest.fixture
def id_type_a(constant_module, constant_creator):
    return constant_creator(
        constant_module._EntityExternalIdCode,
        ID_TYPE_A,
        constant_module.CoreConstants.entity_person,
    )


@pytest.fixture
def id_type_b(constant_module, constant_creator):
    return constant_creator(
        constant_module._EntityExternalIdCode,
        ID_TYPE_B,
        constant_module.CoreConstants.entity_person,
    )


@pytest.fixture
def id_type_c(constant_module, constant_creator):
    return constant_creator(
        constant_module._EntityExternalIdCode,
        ID_TYPE_C,
        constant_module.CoreConstants.entity_person,
    )


@pytest.fixture
def src_foo(constant_module, constant_creator):
    return constant_creator(constant_module._AuthoritativeSystemCode, SRC_FOO)


@pytest.fixture
def src_bar(constant_module, constant_creator):
    return constant_creator(constant_module._AuthoritativeSystemCode, SRC_BAR)


@pytest.fixture
def src_baz(constant_module, constant_creator):
    return constant_creator(constant_module._AuthoritativeSystemCode, SRC_BAZ)


class _IdHelper(object):
    def set(self, person, source, id_type, id_value):
        person._set_external_id(source, id_type, id_value)


@pytest.fixture
def id_types(src_foo, src_bar, src_baz, id_type_a, id_type_b, id_type_c):
    helper = _IdHelper()
    helper.src_foo = src_foo
    helper.src_bar = src_bar
    helper.src_baz = src_baz
    helper.id_a = id_type_a
    helper.id_b = id_type_b
    helper.id_c = id_type_c
    return helper


@pytest.fixture
def person_a(person_creator, id_types):
    person, _ = next(person_creator(1))
    id_types.set(person, id_types.src_foo, id_types.id_a, "a-foo-a")
    id_types.set(person, id_types.src_foo, id_types.id_b, "a-foo-b")
    id_types.set(person, id_types.src_bar, id_types.id_a, "a-bar-a")
    return person


@pytest.fixture
def person_b(person_creator, id_types):
    person, _ = next(person_creator(1))
    id_types.set(person, id_types.src_bar, id_types.id_a, "b-bar-a")
    id_types.set(person, id_types.src_bar, id_types.id_b, "b-bar-b")
    id_types.set(person, id_types.src_baz, id_types.id_a, "b-baz-a")
    return person


@pytest.fixture
def person_c(person_creator, id_types):
    person, _ = next(person_creator(1))
    return person


#
# constant lookup helper tests
#


def test_get_id_types_str(const, id_types):
    expected = (id_types.id_a, id_types.id_b, id_types.id_c)
    lookup_values = [six.text_type(c) for c in expected]
    results = id_export.get_id_types(const, lookup_values)
    assert tuple(results) == expected


def test_get_id_types_verify(const, id_types):
    expected = (id_types.id_a, id_types.id_b, id_types.id_c)
    results = id_export.get_id_types(const, expected)
    assert tuple(results) == expected


def test_get_id_types_invalid(const, id_type_a):
    values = [ID_TYPE_A, ID_TYPE_B]  # ID_TYPE_B doesn't exist yet
    with pytest.raises(LookupError) as exc_info:
        list(id_export.get_id_types(const, values))
    error_msg = six.text_type(exc_info.value)
    assert ID_TYPE_B in error_msg


def test_get_entity_types_verify(const):
    expected = [const.entity_person, const.entity_account]
    results = list(id_export.get_entity_types(const, expected))
    assert results == expected


#
# id fetcher bad init tests
#

def test_init_fetcher_bad_id_type(database):
    with pytest.raises(ValueError) as exc_info:
        id_export.ExternalIdFetcher(database, (INVALID,), None, None)
    error_msg = six.text_type(exc_info.value)
    assert error_msg.startswith("Invalid external id type")
    assert INVALID in error_msg


def test_init_fetcher_empty_id_types(database):
    with pytest.raises(ValueError) as exc_info:
        id_export.ExternalIdFetcher(database, (), None, None)
    error_msg = six.text_type(exc_info.value)
    assert error_msg == "No external id types given"


def test_init_fetcher_duplicate_id_type(database, id_type_a):
    with pytest.raises(ValueError) as exc_info:
        id_export.ExternalIdFetcher(database, (id_type_a, id_type_a),
                                    None, None)
    error_msg = six.text_type(exc_info.value)
    assert error_msg.startswith("Duplicate external id type")
    assert ID_TYPE_A in error_msg


#
# id fetcher result tests
#


def test_fetch_filter(database, const, id_types,
                      person_a, person_b, person_c):
    """ test fetching a narrow selection of data. """
    types = (id_types.id_a,)
    sources = (id_types.src_baz,)
    entity_types = (const.entity_person,)
    fetcher = id_export.ExternalIdFetcher(database, types,
                                          sources, entity_types)
    results = fetcher.get_all()

    # Only person_a has *one* id matching the criterias
    assert len(results) == 1
    assert person_b.entity_id in results
    assert len(results[person_b.entity_id]) == 1


@pytest.fixture
def id_fetcher(database, const, id_types):
    """ an id fetcher that fetches all our fixture types. """
    entity_types = None
    types = (id_types.id_a, id_types.id_b, id_types.id_c)
    sources = (id_types.src_foo, id_types.src_bar, id_types.src_baz)
    return id_export.ExternalIdFetcher(database, types, sources, entity_types)


def test_fetch_all(id_fetcher, person_a, person_b):
    results = id_fetcher.get_all()
    assert len(results) == 2  # 2 persons
    assert len(results[person_a.entity_id]) == 3
    assert len(results[person_b.entity_id]) == 3


def test_fetch_one_hit(id_fetcher, person_a, person_b):
    results = id_fetcher.get_one(person_a.entity_id)
    assert len(results) == 3


def test_fetch_one_miss(id_fetcher, person_a, person_c):
    results = id_fetcher.get_one(person_c.entity_id)
    assert results is base_export.MISSING


#
# id selector tests
#


@pytest.fixture
def id_selector(id_types):
    """ id selector for id-type a, system order (foo, bar, baz). """
    return id_export.ExternalIdSelector([
        (id_types.src_foo, id_types.id_a),
        (id_types.src_bar, id_types.id_a),
        (id_types.src_baz, id_types.id_a),
    ])


def test_select_empty(id_selector):
    assert id_selector([]) == []


def test_select_miss(id_selector, id_types):
    ids = [{
        'source_system': id_types.src_foo,
        'id_type': id_types.id_b,
        'id_value': "foo",
    }]
    assert id_selector(ids) == []


def test_select_hit(id_selector, id_types):
    ids = [
        {
            'source_system': id_types.src_foo,  # has priority
            'id_type': id_types.id_a,
            'id_value': "bar-a",
        },
        {
            'source_system': id_types.src_foo,
            'id_type': id_types.id_b,  # wrong type
            'id_value': "foo-b",
        },
        {
            'source_system': id_types.src_bar,   # not prioritized
            'id_type': id_types.id_a,
            'id_value': "foo-b",
        },
    ]
    assert id_selector(ids) == [ids[0], ids[2]]
    assert id_selector(reversed(ids)) == [ids[0], ids[2]]


def test_select_best_miss(id_selector, id_types):
    ids = [{
        'source_system': id_types.src_foo,
        'id_type': id_types.id_b,
        'id_value': "foo",
    }]
    assert id_selector.get_best_value(ids) is None


def test_select_best_hit(id_selector, id_types):
    ids = [
        {
            'source_system': id_types.src_foo,  # has priority
            'id_type': id_types.id_a,
            'id_value': "bar-a",
        },
        {
            'source_system': id_types.src_foo,
            'id_type': id_types.id_b,  # wrong type
            'id_value': "foo-b",
        },
        {
            'source_system': id_types.src_bar,   # not prioritized
            'id_type': id_types.id_a,
            'id_value': "foo-b",
        },
    ]
    assert id_selector.get_best_value(ids) == "bar-a"


def test_select_invalid_init_duplicate(id_types):
    with pytest.raises(ValueError) as exc_info:
        return id_export.ExternalIdSelector([
            (id_types.src_foo, id_types.id_a),
            (id_types.src_foo, id_types.id_a),
            (id_types.src_baz, id_types.id_b),
        ])

    msg = six.text_type(exc_info.value)
    assert "duplicate selector" in msg.lower()


#
# id cache tests
#


@pytest.fixture
def id_cache(database, const, id_types):
    types = (id_types.id_a, id_types.id_b, id_types.id_c)
    sources = (id_types.src_foo, id_types.src_bar, id_types.src_baz)
    entity_types = (const.entity_person,)
    return id_export.ExternalIdCache(database, types, sources, entity_types)


def test_cache_get(id_cache, person_a, person_b, person_c,
                   id_types):
    result = id_cache.get(person_a.entity_id)
    assert len(result) == 3
    result_keys = set((a['source_system'], a['id_type']) for a in result)
    expect_keys = set([
        (id_types.src_foo, id_types.id_a),
        (id_types.src_foo, id_types.id_b),
        (id_types.src_bar, id_types.id_a),
    ])
    assert result_keys == expect_keys


def test_cache_get_miss(id_cache, person_a, person_b, person_c):
    result = id_cache.get(person_c.entity_id)
    assert result is None


def test_cache_get_again(id_cache, person_a, person_b, person_c):
    result = id_cache.get(person_a.entity_id)
    assert len(result) == 3
    # test cached result for person-a is the same
    assert id_cache.get(person_a.entity_id) == result


def test_cache_get_cached(id_cache, person_a, person_b, person_c):
    id_cache.update_all()

    result = id_cache.get(person_a.entity_id)
    assert len(result) == 3

    result = id_cache.get(person_c.entity_id)
    assert result is None


def test_cache_from_selector(database, id_types):
    sel_a = id_export.ExternalIdSelector([
        (id_types.src_foo, id_types.id_a),
        (id_types.src_bar, id_types.id_a),
    ])
    sel_b = id_export.ExternalIdSelector([
        (id_types.src_bar, id_types.id_b),
        (id_types.src_baz, id_types.id_b),
    ])

    cache = id_export.ExternalIdCache.from_selector(database, sel_a, sel_b)
    assert set(cache.fetcher.id_types) == set((id_types.id_a, id_types.id_b))
    assert set(cache.fetcher.source_systems) == set((id_types.src_foo,
                                                     id_types.src_bar,
                                                     id_types.src_baz))
    assert cache.fetcher.entity_types is None
