# encoding: utf-8
"""
Unit tests for :mod:`Cerebrum.export.contacts`.

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

from Cerebrum.export import contacts as c_export
from Cerebrum.export import base as base_export


#
# Some contact types and source systems
#


C_TYPE_A = "c-a-c1c8 MOBILE"
C_TYPE_B = "c-b-6ff4 PHONE"
C_TYPE_C = "c-c-3946 EMAIL"

SRC_FOO = "s-foo-a04f36c6"
SRC_BAR = "s-bar-a04f36c7"
SRC_BAZ = "s-baz-a04f36c8"

# A generic, non-existing code value (of any type)
INVALID = "missing-dea105ef"


@pytest.fixture
def c_type_a(constant_module, constant_creator):
    return constant_creator(constant_module._ContactInfoCode, C_TYPE_A)


@pytest.fixture
def c_type_b(constant_module, constant_creator):
    return constant_creator(constant_module._ContactInfoCode, C_TYPE_B)


@pytest.fixture
def c_type_c(constant_module, constant_creator):
    return constant_creator(constant_module._ContactInfoCode, C_TYPE_C)


@pytest.fixture
def src_foo(constant_module, constant_creator):
    return constant_creator(constant_module._AuthoritativeSystemCode, SRC_FOO)


@pytest.fixture
def src_bar(constant_module, constant_creator):
    return constant_creator(constant_module._AuthoritativeSystemCode, SRC_BAR)


@pytest.fixture
def src_baz(constant_module, constant_creator):
    return constant_creator(constant_module._AuthoritativeSystemCode, SRC_BAZ)


class _DataHelper(object):

    def __init__(self):
        self.pref = 1

    def set(self, person, source, c_type, c_value):
        person.add_contact_info(source, c_type, c_value, pref=self.pref)
        self.pref += 1


@pytest.fixture
def helper(src_foo, src_bar, src_baz, c_type_a, c_type_b, c_type_c):
    obj = _DataHelper()
    obj.src_foo = src_foo
    obj.src_bar = src_bar
    obj.src_baz = src_baz
    obj.a = c_type_a
    obj.b = c_type_b
    obj.c = c_type_c
    return obj


@pytest.fixture
def person_a(person_creator, helper):
    person, _ = next(person_creator(1))
    helper.set(person, helper.src_foo, helper.a, "a-foo-a")
    helper.set(person, helper.src_foo, helper.b, "a-foo-b")
    helper.set(person, helper.src_bar, helper.a, "a-bar-a")
    return person


@pytest.fixture
def person_b(person_creator, helper):
    person, _ = next(person_creator(1))
    helper.set(person, helper.src_bar, helper.a, "b-bar-a")
    helper.set(person, helper.src_bar, helper.b, "b-bar-b")
    helper.set(person, helper.src_baz, helper.a, "b-baz-a")
    return person


@pytest.fixture
def person_c(person_creator, helper):
    person, _ = next(person_creator(1))
    return person


#
# constant lookup helper tests
#


def test_get_contact_types_str(const, helper):
    expected = (helper.a, helper.b, helper.c)
    lookup_values = [six.text_type(c) for c in expected]
    results = c_export.get_contact_types(const, lookup_values)
    assert tuple(results) == expected


def test_get_contact_types_verify(const, helper):
    expected = (helper.a, helper.b, helper.c)
    results = c_export.get_contact_types(const, expected)
    assert tuple(results) == expected


def test_get_contact_types_invalid(const, c_type_a):
    values = [C_TYPE_A, C_TYPE_B]  # C_TYPE_B doesn't exist yet
    with pytest.raises(LookupError) as exc_info:
        list(c_export.get_contact_types(const, values))
    error_msg = six.text_type(exc_info.value)
    assert C_TYPE_B in error_msg


def test_get_entity_types_verify(const):
    expected = [const.entity_person, const.entity_account]
    results = list(c_export.get_entity_types(const, expected))
    assert results == expected


#
# contact fetcher bad init tests
#

def test_init_fetcher_bad_contact_type(database):
    with pytest.raises(ValueError) as exc_info:
        c_export._ContactInfoFetcher(database, (INVALID,), None, None)
    error_msg = six.text_type(exc_info.value)
    assert error_msg.startswith("Invalid contact type")
    assert INVALID in error_msg


def test_init_fetcher_duplicate_contact_type(database, c_type_a):
    with pytest.raises(ValueError) as exc_info:
        c_export._ContactInfoFetcher(database, (c_type_a, c_type_a),
                                     None, None)
    error_msg = six.text_type(exc_info.value)
    assert error_msg.startswith("Duplicate contact type")
    assert C_TYPE_A in error_msg


#
# contact fetcher result tests
#


def test_fetch_filter(database, const, helper,
                      person_a, person_b, person_c):
    """ test fetching a narrow selection of data. """
    types = (helper.a,)
    sources = (helper.src_baz,)
    entity_types = (const.entity_person,)
    fetcher = c_export._ContactInfoFetcher(database, types, sources,
                                           entity_types)
    results = fetcher.get_all()

    # Only person_a has *one* id matching the criterias
    assert len(results) == 1
    assert person_b.entity_id in results
    assert len(results[person_b.entity_id]) == 1


@pytest.fixture
def contact_fetcher(database, const, helper):
    """ an id fetcher that fetches all our fixture types. """
    entity_types = None
    types = (helper.a, helper.b, helper.c)
    sources = (helper.src_foo, helper.src_bar, helper.src_baz)
    return c_export._ContactInfoFetcher(database, types, sources, entity_types)


def test_fetch_all(contact_fetcher, person_a, person_b):
    results = contact_fetcher.get_all()
    assert len(results) == 2  # 2 persons
    assert len(results[person_a.entity_id]) == 3
    assert len(results[person_b.entity_id]) == 3


def test_fetch_one_hit(contact_fetcher, person_a, person_b):
    results = contact_fetcher.get_one(person_a.entity_id)
    assert len(results) == 3


def test_fetch_one_miss(contact_fetcher, person_a, person_c):
    results = contact_fetcher.get_one(person_c.entity_id)
    assert results is base_export.MISSING


#
# legacy contact fetcher normalization tests
#


@pytest.fixture
def legacy_fetcher(database, const, helper):
    """ an id fetcher that fetches all our fixture types. """
    entity_types = None
    types = (helper.a, helper.b, helper.c)
    sources = (helper.src_foo, helper.src_bar, helper.src_baz)
    return c_export._LegacyDataMixin(database, types, sources, entity_types)


def test_fetch_legacy_sep(legacy_fetcher, helper, person_c):
    helper.set(person_c, helper.src_foo, helper.a, "foo$bar")
    result = legacy_fetcher.get_one(person_c.entity_id)
    assert len(result) == 1
    assert result[0]['contact_value'] == "foo"


def test_fetch_legacy_sep_skip_empty(legacy_fetcher, helper, person_c):
    helper.set(person_c, helper.src_foo, helper.a, "$bar")
    result = legacy_fetcher.get_one(person_c.entity_id)
    assert len(result) == 1
    assert result[0]['contact_value'] == "bar"


def test_fetch_legacy_sep_omit_empty(legacy_fetcher, helper, person_c):
    helper.set(person_c, helper.src_foo, helper.a, "$")
    result = legacy_fetcher.get_one(person_c.entity_id)
    assert result is base_export.MISSING


def test_fetch_legacy_phone(legacy_fetcher, helper, person_c):
    helper.set(person_c, helper.src_foo, helper.a, "foo/bar")
    result = legacy_fetcher.get_one(person_c.entity_id)
    assert len(result) == 1
    assert result[0]['contact_value'] == "foo"


def test_fetch_legacy_phone_sep_combined(legacy_fetcher, helper, person_c):
    helper.set(person_c, helper.src_foo, helper.a, "/bar$baz")
    result = legacy_fetcher.get_one(person_c.entity_id)
    assert len(result) == 1
    assert result[0]['contact_value'] == "bar"


def test_fetch_legacy_phone_sep_missing(legacy_fetcher, helper, person_c):
    helper.set(person_c, helper.src_foo, helper.a, "/$")
    result = legacy_fetcher.get_one(person_c.entity_id)
    assert result is base_export.MISSING

#
# contact selector tests
#


@pytest.fixture
def contact_selector(helper):
    """ id selector for id-type a, system order (foo, bar, baz). """
    return c_export.ContactInfoSelector([
        (helper.src_foo, helper.a),
        (helper.src_bar, helper.a),
        (helper.src_baz, helper.a),
    ])


def test_select_empty(contact_selector):
    assert contact_selector([]) == []


def test_select_miss(contact_selector, helper):
    contacts = [{
        'source_system': helper.src_foo,
        'contact_type': helper.b,
        'contact_value': "foo",
        'contact_pref': 0,
    }]
    assert contact_selector(contacts) == []


def test_select_hit(contact_selector, helper):
    contacts = [
        {
            'source_system': helper.src_foo,  # has priority
            'contact_type': helper.a,
            'contact_value': "bar-a",
            'contact_pref': 0,
        },
        {
            'source_system': helper.src_foo,
            'contact_type': helper.b,  # wrong type
            'contact_value': "foo-b",
            'contact_pref': 0,
        },
        {
            'source_system': helper.src_bar,   # not prioritized
            'contact_type': helper.a,
            'contact_value': "foo-b",
            'contact_pref': 0,
        },
    ]
    assert contact_selector(contacts) == [contacts[0], contacts[2]]
    assert contact_selector(reversed(contacts)) == [contacts[0], contacts[2]]


def test_select_duplicate(contact_selector, helper):
    contacts = [
        {
            'source_system': helper.src_foo,
            'contact_type': helper.a,
            'contact_value': "last-a",
            'contact_pref': 9,
        },
        {
            'source_system': helper.src_foo,
            'contact_type': helper.a,
            'contact_value': "first-a",
            'contact_pref': 4,
        },
        {
            'source_system': helper.src_bar,
            'contact_type': helper.a,
            'contact_value': "foo-b",
            'contact_pref': 1,
        },
    ]
    expected = [contacts[1], contacts[0], contacts[2]]
    assert contact_selector(contacts) == expected
    assert contact_selector(reversed(contacts)) == expected


def test_select_best_miss(contact_selector, helper):
    contacts = [{
        'source_system': helper.src_foo,
        'contact_type': helper.b,
        'contact_value': "foo",
        'contact_pref': 0,
    }]
    assert contact_selector.get_best_value(contacts) is None


def test_select_best_hit(contact_selector, helper):
    contacts = [
        {
            'source_system': helper.src_foo,  # has priority
            'contact_type': helper.a,
            'contact_value': "bar-a",
            'contact_pref': 0,
        },
        {
            'source_system': helper.src_foo,
            'contact_type': helper.b,  # wrong type
            'contact_value': "foo-b",
            'contact_pref': 0,
        },
        {
            'source_system': helper.src_bar,   # not prioritized
            'contact_type': helper.a,
            'contact_value': "foo-b",
            'contact_pref': 0,
        },
    ]
    assert contact_selector.get_best_value(contacts) == "bar-a"


def test_select_invalid_init_duplicate(helper):
    with pytest.raises(ValueError) as exc_info:
        return c_export.ContactInfoSelector([
            (helper.src_foo, helper.a),
            (helper.src_foo, helper.a),
            (helper.src_baz, helper.b),
        ])

    msg = six.text_type(exc_info.value)
    assert "duplicate selector" in msg.lower()


#
# id cache tests
#


@pytest.fixture
def contact_cache(database, const, helper):
    types = (helper.a, helper.b, helper.c)
    sources = (helper.src_foo, helper.src_bar, helper.src_baz)
    entity_types = (const.entity_person,)
    return c_export.ContactInfoCache(database, types, sources, entity_types)


def test_cache_get(contact_cache, helper, person_a, person_b, person_c):
    result = contact_cache.get(person_a.entity_id)
    assert len(result) == 3
    result_keys = set((a['source_system'], a['contact_type']) for a in result)
    expect_keys = set([
        (helper.src_foo, helper.a),
        (helper.src_foo, helper.b),
        (helper.src_bar, helper.a),
    ])
    assert result_keys == expect_keys


def test_cache_get_miss(contact_cache, person_a, person_b, person_c):
    result = contact_cache.get(person_c.entity_id)
    assert result is None


def test_cache_get_again(contact_cache, person_a, person_b, person_c):
    result = contact_cache.get(person_a.entity_id)
    assert len(result) == 3
    # test cached result for person-a is the same
    assert contact_cache.get(person_a.entity_id) == result


def test_cache_get_cached(contact_cache, person_a, person_b, person_c):
    contact_cache.update_all()

    result = contact_cache.get(person_a.entity_id)
    assert len(result) == 3

    result = contact_cache.get(person_c.entity_id)
    assert result is None


def test_cache_from_selector(database, helper):
    sel_a = c_export.ContactInfoSelector([
        (helper.src_foo, helper.a),
        (helper.src_bar, helper.a),
    ])
    sel_b = c_export.ContactInfoSelector([
        (helper.src_bar, helper.b),
        (helper.src_baz, helper.b),
    ])

    cache = c_export.ContactInfoCache.from_selector(database, sel_a, sel_b)
    assert set(cache.fetcher.contact_types) == set((helper.a, helper.b))
    assert set(cache.fetcher.source_systems) == set((helper.src_foo,
                                                     helper.src_bar,
                                                     helper.src_baz))
    assert cache.fetcher.entity_types is None
