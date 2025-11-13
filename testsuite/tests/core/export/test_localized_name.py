# encoding: utf-8
"""
Unit tests for :mod:`Cerebrum.export.localized_name`.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest
import six

from Cerebrum.export import localized_name as name_export
from Cerebrum.export import base as base_export


#
# Name types
#


NAME_FOO = "name-foo-9d1a62"
NAME_BAR = "name-bar-23b691"

# A generic, non-existing code value (of any type)
INVALID = "missing-dea105ef"


@pytest.fixture
def create_name_type(constant_module, constant_creator):
    def create_name(strval):
        return constant_creator(
            constant_module._EntityNameCode,
            strval,
            description=(
                "Cerebrum.export.localized_name test name {}".format(strval)
            ),
            lang={
                'nb': "Testnavn {}".format(strval),
                'en': "Test name {}".format(strval),
            },
        )
    return create_name


@pytest.fixture
def name_foo(create_name_type):
    return create_name_type(NAME_FOO)


@pytest.fixture
def name_bar(create_name_type):
    return create_name_type(NAME_BAR)


# ... and some example data and helpers


@pytest.fixture
def person_a(person_creator, const, name_foo, name_bar):
    person, _ = next(person_creator(1))
    # add_name_with_language requires the language as an intval...
    person.add_name_with_language(name_foo, int(const.language_nb), "nb-foo-a")
    person.add_name_with_language(name_foo, int(const.language_en), "en-foo-a")
    person.add_name_with_language(name_foo, int(const.language_nn), "nn-foo-a")
    return person


@pytest.fixture
def person_b(person_creator, const, name_foo, name_bar):
    person, _ = next(person_creator(1))
    person.add_name_with_language(name_foo, int(const.language_nb), "nb-foo-b")
    person.add_name_with_language(name_bar, int(const.language_en), "en-bar-b")
    return person


@pytest.fixture
def person_c(person_creator):
    person, _ = next(person_creator(1))
    return person


#
# constant lookup helper tests
#


def test_get_name_types_str(const, name_foo, name_bar):
    values = [NAME_FOO, NAME_BAR]
    results = name_export.get_name_types(const, values)
    assert tuple(results) == (name_foo, name_bar)


def test_get_name_types_verify(const, name_foo, name_bar):
    values = (name_foo, name_bar)
    results = name_export.get_name_types(const, values)
    assert tuple(results) == values


def test_get_name_types_invalid(const, name_foo):
    values = [NAME_FOO, NAME_BAR]  # NAME_BAR doesn't exist yet
    with pytest.raises(LookupError) as exc_info:
        list(name_export.get_name_types(const, values))
    error_msg = six.text_type(exc_info.value)
    assert NAME_BAR in error_msg


def test_get_entity_types_verify(const):
    expected = [const.entity_person, const.entity_account]
    results = list(name_export.get_entity_types(const, expected))
    assert results == expected


def test_get_name_languages_verify(const):
    expected = [const.language_nb, const.language_nn, const.language_en]
    results = list(name_export.get_name_languages(const, expected))
    assert results == expected


#
# name fetcher bad init tests
#


def test_init_fetcher_bad_name(database):
    with pytest.raises(ValueError) as exc_info:
        name_export.NameFetcher(database, (INVALID,), None, None)
    error_msg = six.text_type(exc_info.value)
    assert error_msg.startswith("Invalid name type")
    assert INVALID in error_msg


def test_init_fetcher_empty_id_types(database):
    with pytest.raises(ValueError) as exc_info:
        name_export.NameFetcher(database, (), None, None)
    error_msg = six.text_type(exc_info.value)
    assert error_msg == "No name types given"


def test_init_fetcher_duplicate_name_type(database, name_foo):
    with pytest.raises(ValueError) as exc_info:
        name_export.NameFetcher(database, (name_foo, name_foo), None, None)
    error_msg = six.text_type(exc_info.value)
    assert error_msg.startswith("Duplicate name type")
    assert NAME_FOO in error_msg


#
# name fetcher result tests
#


def test_fetch_filter(database, const, name_bar,
                      person_a, person_b, person_c):
    """ test fetching a narrow selection of data. """
    types = (name_bar,)
    languages = (const.language_en,)
    entity_types = (const.entity_person,)
    fetcher = name_export.NameFetcher(database, types, languages, entity_types)
    results = fetcher.get_all()

    # Only person_a has *one* id matching the criterias
    assert len(results) == 1
    assert person_b.entity_id in results
    assert len(results[person_b.entity_id]) == 1


@pytest.fixture
def name_fetcher(database, const, name_foo, name_bar):
    """ an id fetcher that fetches all our fixture types. """
    types = (name_foo, name_bar)
    return name_export.NameFetcher(database, types, None, None)


def test_fetch_all(name_fetcher, person_a, person_b, person_c):
    results = name_fetcher.get_all()
    assert len(results) == 2  # 2 persons
    assert len(results[person_a.entity_id]) == 3
    assert len(results[person_b.entity_id]) == 2


def test_fetch_one_hit(name_fetcher, person_a, person_b):
    results = name_fetcher.get_one(person_a.entity_id)
    assert len(results) == 3


def test_fetch_one_miss(name_fetcher, person_a, person_c):
    results = name_fetcher.get_one(person_c.entity_id)
    assert results is base_export.MISSING


#
# name cache tests
#


@pytest.fixture
def name_cache(database, const, name_foo, name_bar):
    types = (name_foo, name_bar)
    return name_export.NameCache(database, types, None, None)


def test_cache_get(name_cache, person_a, person_b, person_c,
                   const, name_foo):
    result = name_cache.get(person_a.entity_id)
    assert len(result) == 3
    result_keys = set((a['name_variant'], a['name_language']) for a in result)
    expect_keys = set([
        (name_foo, const.language_nb),
        (name_foo, const.language_nn),
        (name_foo, const.language_en),
    ])
    assert result_keys == expect_keys


def test_cache_get_miss(name_cache, person_a, person_b, person_c):
    result = name_cache.get(person_c.entity_id)
    assert result is None


def test_cache_get_again(name_cache, person_a, person_b, person_c):
    result = name_cache.get(person_a.entity_id)
    assert len(result) == 3
    # test cached result for person-a is the same
    assert name_cache.get(person_a.entity_id) == result


def test_cache_get_cached(name_cache, person_a, person_b, person_c):
    name_cache.update_all()

    result = name_cache.get(person_a.entity_id)
    assert len(result) == 3

    result = name_cache.get(person_c.entity_id)
    assert result is None


#
# name selector tests
#


@pytest.fixture
def name_selector(const, name_foo, name_bar):
    """ id selector for id-type a, system order (foo, bar, baz). """
    return name_export.NameSelector([
        (name_foo, const.language_nb),
        (name_foo, const.language_en),
    ])


def test_select_empty(name_selector):
    assert name_selector([]) == []


def test_select_miss(name_selector, const, name_bar):
    names = [{
        'name_variant': name_bar,
        'name_language': const.language_nb,
        'name': "foo",
    }]
    assert name_selector(names) == []


def test_select_hit(name_selector, const, name_foo, name_bar):
    names = [
        {
            'name_variant': name_foo,
            'name_language': const.language_en,
            'name': "foo",
        },
        {
            'name_variant': name_bar,
            'name_language': const.language_nb,
            'name': "foo",
        },
        {
            'name_variant': name_foo,
            'name_language': const.language_nb,
            'name': "foo",
        },
    ]
    expected = [names[2], names[0]]
    assert name_selector(names) == expected
    assert name_selector(reversed(names)) == expected


def test_select_invalid_init_duplicate(const, name_foo, name_bar):
    with pytest.raises(ValueError) as exc_info:
        return name_export.NameSelector([
            (name_foo, const.language_nb),
            (name_foo, const.language_en),
            (name_foo, const.language_nb),
        ])

    msg = six.text_type(exc_info.value)
    assert "duplicate value" in msg.lower()


#
# Test grouping helpers
#


def test_group_names_by_type():
    names = [
        ("foo", "en", "foo-en"),
        ("foo", "nb", "foo-nb"),
        ("bar", "nb", "bar-nb"),
        ("bar", "en", "bar-en"),
    ]
    expected = [
        ("foo", [("en", "foo-en"), ("nb", "foo-nb")]),
        ("bar", [("nb", "bar-nb"), ("en", "bar-en")]),
    ]
    result = list(name_export.group_names_by_type(names))
    assert result == expected


def test_group_names_by_language():
    names = [
        ("foo", "en", "foo-en"),
        ("foo", "nb", "foo-nb"),
        ("bar", "nb", "bar-nb"),
        ("bar", "en", "bar-en"),
    ]
    expected = [
        ("en", [("foo", "foo-en"), ("bar", "bar-en")]),
        ("nb", [("foo", "foo-nb"), ("bar", "bar-nb")]),
    ]
    result = list(name_export.group_names_by_language(names))
    assert result == expected
