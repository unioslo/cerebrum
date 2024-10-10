# -*- coding: utf-8 -*-
"""
Tests for :mod:`Cerebrum.modules.EntityTrait`

TODO: This module should be re-factored and moved to
`Cerebrum.modules.trait.mixins`
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

from Cerebrum import Errors
from Cerebrum.modules.EntityTrait import EntityTrait
from Cerebrum.modules.trait import trait_db


# Fixtures
#
# Note: person traits `trait_{a,b,c,d}` are defined in `conftest`


@pytest.fixture
def person_cls(person_cls):
    # Override `person_cls` for `person_creator` to ensure it has a
    # `EntityTrait` mixin.
    target_cls = EntityTrait
    if target_cls in person_cls.mro():
        return person_cls
    else:
        class TraitPerson(person_cls, target_cls):
            pass

        return TraitPerson


@pytest.fixture
def person(person_creator):
    person, _ = next(person_creator(1))
    return person


@pytest.fixture
def get_traits(database, person):
    """ helper to get traits from our person fixture. """
    entity_id = int(person.entity_id)

    def _get_traits(**kwargs):
        return list(trait_db.search_traits(database,
                                           entity_id=entity_id,
                                           **kwargs))
    return _get_traits


def test_populate_traits(person, get_traits, trait_a, trait_b):
    person.populate_trait(trait_a, date=datetime.date.today())
    person.populate_trait(trait_b, strval="example")
    results = get_traits()
    assert len(results) == 0
    person.write_db()
    results = get_traits()
    assert len(results) == 2


def test_update_trait(person, get_traits, trait_a):
    person.populate_trait(trait_a, numval=10)
    person.write_db()

    person.populate_trait(trait_a, numval=15)
    person.write_db()

    results = get_traits()
    assert len(results) == 1
    assert results[0]['numval'] == 15


def test_delete_trait(person, get_traits, trait_a, trait_b):
    person.populate_trait(trait_a, numval=3)
    person.populate_trait(trait_b, strval="example")
    person.write_db()

    person.delete_trait(trait_a)
    person.write_db()
    results = get_traits()
    assert len(results) == 1


def test_delete_missing_trait(person, trait_a):
    with pytest.raises(Errors.NotFoundError) as exc_info:
        person.delete_trait(trait_a)

    error_msg = six.text_type(exc_info.value)
    assert six.text_type(trait_a) in error_msg


def test_delete_unwritten_new_trait(person, get_traits, trait_a):
    person.populate_trait(trait_a, numval=3)
    person.delete_trait(trait_a)
    person.write_db()
    results = get_traits()
    assert len(results) == 0


def test_delete_unwritten_trait_update(person, get_traits, trait_a):
    person.populate_trait(trait_a, numval=3)
    person.write_db()

    person.populate_trait(trait_a, numval=4)
    person.delete_trait(trait_a)
    person.write_db()
    results = get_traits()
    assert len(results) == 0


def test_delete_race_condition(person, get_traits, trait_a):
    person.populate_trait(trait_a, numval=3)
    person.write_db()
    trait_db.clear_trait(person._db, person.entity_id, trait_a)

    # trait is now cached in person object, but removed from db
    person.delete_trait(trait_a)
    person.write_db()
    results = get_traits()
    assert len(results) == 0


def test_delete_person(person, get_traits, trait_a):
    person.populate_trait(trait_a, numval=3)
    person.write_db()

    person.delete()
    results = get_traits()
    assert len(results) == 0


def test_get_traits(person, trait_a, trait_b):
    person.populate_trait(trait_a, numval=3)
    person.populate_trait(trait_b, strval="example")
    person.write_db()

    traits = person.get_traits()
    assert len(traits) == 2


def test_get_traits_uncached(person, trait_a, trait_b):
    person.populate_trait(trait_a, numval=3)
    person.populate_trait(trait_b, strval="example")
    person.write_db()

    entity_id = person.entity_id
    person.clear()
    person.find(entity_id)

    traits = person.get_traits()
    assert len(traits) == 2


def test_get_trait(person, trait_a, trait_b):
    person.populate_trait(trait_a, numval=3)
    person.populate_trait(trait_b, strval="example")
    person.write_db()

    trait_data = person.get_trait(trait_a)
    assert trait_data['numval'] == 3


def test_get_trait_missing(person, trait_a):
    trait_data = person.get_trait(trait_a)
    assert not trait_data


def trait_list(iterable):
    return sorted(
        [dict(r) for r in iterable],
        key=lambda r: (r['entity_id'], r['code']),
    )


def test_list_traits(person, get_traits, trait_a, trait_b):
    person.populate_trait(trait_a, numval=3)
    person.populate_trait(trait_b, strval="example")
    person.write_db()

    expected = trait_list(get_traits())
    results = trait_list(person.list_traits(entity_id=person.entity_id))
    assert results == expected


def test_list_traits_unset(person, get_traits, trait_a, trait_b):
    person.populate_trait(trait_a, numval=3)
    person.populate_trait(trait_b)
    person.write_db()

    expected = trait_list(get_traits(numval=None))
    results = trait_list(person.list_traits(entity_id=person.entity_id,
                                            numval=None))
    assert results == expected


def test_list_traits_sequence(person, get_traits, trait_a, trait_b):
    person.populate_trait(trait_a, numval=3)
    person.populate_trait(trait_b, numval=5)
    person.write_db()

    expected = trait_list(get_traits(numval=(1, 2, 3)))
    results = trait_list(person.list_traits(entity_id=person.entity_id,
                                            numval=(1, 2, 3)))
    assert results == expected


def test_list_traits_empty_sequence(person, get_traits, trait_a, trait_b):
    # This is very odd behaviour in EntityTrait.list_traits(), but an empty
    # <field> sequence is the same as searching for `<field>=None`
    # This should probably be re-factored...
    person.populate_trait(trait_a, numval=3)
    person.populate_trait(trait_b)
    person.write_db()

    expected = trait_list(get_traits(numval=None))
    results = trait_list(person.list_traits(entity_id=person.entity_id,
                                            numval=()))
    assert results == expected


def test_list_traits_pattern(person, get_traits, trait_a, trait_b, trait_c):
    # This is very odd behaviour in EntityTrait.list_traits(), but it's
    # possible to use both strval and strval_like - and in this case, strval is
    # ignored.
    #
    # Also, strval_like does not properly escape the input string, so that:
    #
    # 1. It's not possible to search for a literal wildcard char
    # 2. It's possible to use sql wildcards in addition to glob wildcards
    #
    # This should probably be re-factored...
    person.populate_trait(trait_a, strval="Foo Bar")
    person.populate_trait(trait_b, strval="foo bar")
    person.populate_trait(trait_c, strval="bar baz")
    person.write_db()

    expected = trait_list(get_traits(strval_ilike="foo *"))
    results = trait_list(person.list_traits(entity_id=person.entity_id,
                                            strval_like="foo %",
                                            strval="bar baz"))
    assert results == expected


def test_list_traits_pattern_smart_case(person, get_traits, trait_a, trait_b):
    # This is probably unwanted behaviour in EntityTrait.list_traits(), but
    # it's not possible to specify if case sensitivity.  By default, case
    # sensitivity is enabled if the input uses upper case characters.
    #
    # This should probably be re-factored...
    person.populate_trait(trait_a, strval="Foo Bar")
    person.populate_trait(trait_b, strval="foo bar")
    person.write_db()

    expected = trait_list(get_traits(strval_like="Foo *"))
    results = trait_list(person.list_traits(entity_id=person.entity_id,
                                            strval_like="Foo %"))
    assert results == expected
