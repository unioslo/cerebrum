# -*- coding: utf-8 -*-
""" Tests for :mod:`Cerebrum.modules.trait.trait_db` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime

import pytest
import six

from Cerebrum.modules.trait import trait_db
from Cerebrum.utils import date_compat


# Fixtures
#
# Note: person traits `trait_{a,b,c,d}` are defined in `conftest`


@pytest.fixture
def set_traits(database, trait_a, trait_b, trait_c, trait_d):
    def _setter(person, a=None, b=None, c=None, d=None):
        results = []
        for trait, value in ((trait_a, a), (trait_b, b),
                             (trait_c, c), (trait_d, d)):
            if value is None:
                continue
            kwargs = dict(value)
            row = trait_db.set_trait(
                database,
                entity_id=person.entity_id,
                entity_type=person.entity_type,
                code=trait,
                **kwargs
            )
            results.append(dict(row))
        return results

    # An attribute tu use for filtering our trait types in `search_traits()`
    setattr(_setter, "codes", (trait_a, trait_b, trait_c, trait_d))

    # Convenience access to trait codes
    setattr(_setter, "a", trait_a)
    setattr(_setter, "b", trait_b)
    setattr(_setter, "c", trait_c)
    setattr(_setter, "d", trait_d)

    return _setter


@pytest.fixture
def person(person_creator):
    person, _ = next(person_creator(1))
    return person


#
# set_trait tests
#


def test_set_trait(database, person, trait_a):
    trait_data = {
        'entity_id': int(person.entity_id),
        'entity_type': int(person.entity_type),
        'code': int(trait_a),
        'target_id': int(person.entity_id),
        'date': datetime.date(1998, 6, 28),
        'numval': 3,
        'strval': "example text",
    }

    result = dict(trait_db.set_trait(database, **trait_data))
    result['date'] = date_compat.get_date(result['date'])
    assert result == trait_data


def test_set_trait_without_fields(database, person, trait_a):
    result = trait_db.set_trait(database, person.entity_id,
                                person.entity_type, trait_a)
    assert result['entity_id'] == person.entity_id
    assert result['entity_type'] == person.entity_type
    assert result['code'] == trait_a
    assert all(result[k] is None
               for k in ('target_id', 'date', 'numval', 'strval'))


def test_set_trait_update(database, person, trait_a):
    args = (database, person.entity_id, person.entity_type, trait_a)
    trait_db.set_trait(*args, numval=3)

    result = trait_db.set_trait(*args, numval=4)
    assert result['entity_id'] == person.entity_id
    assert result['entity_type'] == person.entity_type
    assert result['code'] == trait_a
    assert result['numval'] == 4


def test_set_trait_noop(database, person, trait_a):
    args = (database, person.entity_id, person.entity_type, trait_a)
    trait_db.set_trait(*args, numval=3)

    result = trait_db.set_trait(*args, numval=3)
    assert result['entity_id'] == person.entity_id
    assert result['entity_type'] == person.entity_type
    assert result['code'] == trait_a
    assert result['numval'] == 3


#
# get_trait tests
#


def test_get_trait_miss(database, person, trait_a):
    """ ``get_trait()`` returns ``None`` if no trait is set. """
    result = trait_db.get_trait(database, person.entity_id, trait_a)
    assert result is None


@pytest.fixture
def trait(database, person, trait_a):
    """ a *trait_a* for *person* with numval=3. """
    return dict(trait_db.set_trait(database, person.entity_id,
                                   person.entity_type, trait_a, numval=3))


def test_get_trait_hit(database, person, trait_a, trait):
    """ ``get_trait()`` returns a trait row if the trait exists. """
    result = trait_db.get_trait(database, person.entity_id, trait_a)
    assert result
    assert dict(result) == trait


def test_get_trait_value_hit(database, person, trait_a, trait):
    """ ``get_trait()`` only returns a matching row. """
    result = trait_db.get_trait(database, person.entity_id, trait_a,
                                numval=3)
    assert result


def test_get_trait_value_miss(database, person, trait_a, trait):
    """ ``get_trait()`` returns ``None`` if no matching row exists. """
    result = trait_db.get_trait(database, person.entity_id, trait_a,
                                numval=4)
    assert not result


#
# clear_trait tests
#


def test_clear_trait_noop(database, person, trait_a):
    """ ``clear_trait()`` returns ``None`` if no trait was set. """
    result = trait_db.clear_trait(database, person.entity_id, trait_a)
    assert result is None


def test_clear_trait(database, person, trait_a, trait):
    """ ``clear_trait()`` returns the removed row. """
    result = trait_db.clear_trait(database, person.entity_id, trait_a)
    assert result['entity_id'] == person.entity_id
    assert result['entity_type'] == person.entity_type
    assert result['code'] == trait_a
    assert result['numval'] == 3
    assert not trait_db.get_trait(database, person.entity_id, trait_a)


#
# search tests
#
# `search_traits` is just a thin wrapper around the `_select()` function for
# creating conditions and binds.  `_select()` is also used to generate queries
# for the `get_trait` and `delete_traits` functions.  Most of the stuff tested
# here will also cover those functions.
#


def test_search_empty(database, trait_a):
    assert list(trait_db.search_traits(database, code=trait_a)) == []


def test_search_limit(database, person, set_traits):
    set_traits(person, a={}, b={}, c={})
    results = list(trait_db.search_traits(database,
                                          entity_id=person.entity_id,
                                          limit=2))
    assert len(results) == 2


def test_search_entity_type(database, person, set_traits):
    set_traits(person, a={}, b={}, c={})
    results = list(trait_db.search_traits(database,
                                          code=set_traits.codes,
                                          entity_type=person.entity_type))
    assert len(results) == 3


def test_search_target_id(database, person, set_traits):
    target_id = person.entity_id
    set_traits(
        person,
        a={'target_id': target_id},
        b={},
        c={'target_id': target_id},
    )
    results = list(trait_db.search_traits(database,
                                          code=set_traits.codes,
                                          target_id=target_id))
    assert len(results) == 2


def test_search_target_id_unset(database, person, set_traits):
    target_id = person.entity_id
    set_traits(
        person,
        a={'target_id': target_id},
        b={},
        c={'target_id': target_id},
    )
    results = list(trait_db.search_traits(database,
                                          code=set_traits.codes,
                                          target_id=None))
    assert len(results) == 1


def test_search_date_range(database, person, trait_a, trait_b):
    t = datetime.date.today()
    d = datetime.timedelta
    args = (database, person.entity_id, person.entity_type)
    trait_db.set_trait(*args, code=trait_a, date=t)
    trait_db.set_trait(*args, code=trait_b, date=(t - d(days=7)))

    results = list(trait_db.search_traits(database,
                                          code=(trait_a, trait_b),
                                          date_after=(t - d(days=4)),
                                          date_before=(t + d(days=4))))
    assert len(results) == 1
    assert results[0]['code'] == trait_a


def test_search_date_range_invalid(database, person):
    t = datetime.date.today()
    d = datetime.timedelta
    with pytest.raises(ValueError) as exc_info:
        trait_db.search_traits(database, entity_id=person.entity_id,
                               date_after=(t - d(days=2)),
                               date_before=(t - d(days=4)))

    error_msg = six.text_type(exc_info.value)
    assert "invalid range" in error_msg


@pytest.fixture
def numvals(database, person, set_traits):
    return set_traits(
        person,
        a={'numval': 30},
        b={'numval': 40},
        c={'numval': 50},
        d={},
    )


def test_search_numval_min(database, person, numvals):
    results = list(trait_db.search_traits(database,
                                          entity_id=person.entity_id,
                                          numval_min=40))
    assert len(results) == 2
    assert set(r['numval'] for r in results) == set((40, 50))


def test_search_numval_max(database, person, numvals):
    results = list(trait_db.search_traits(database,
                                          entity_id=person.entity_id,
                                          numval_max=40))
    assert len(results) == 1
    assert set(r['numval'] for r in results) == set((30,))


def test_search_numval_combined(database, person, numvals):
    """ search can combine a specific numval and a numval range. """
    results = list(trait_db.search_traits(database,
                                          entity_id=person.entity_id,
                                          numval=50,
                                          numval_max=40))
    assert len(results) == 2
    assert set(r['numval'] for r in results) == set((30, 50))


def test_search_numval(database, person, numvals):
    """ test searching for a numval sequence. """
    target = (30, 40)
    results = list(trait_db.search_traits(database,
                                          entity_id=person.entity_id,
                                          numval=target))
    assert len(results) == 2
    assert set(r['numval'] for r in results) == set(target)


def test_search_numval_invalid(database, person):
    """ searching for an invalid numval range is an error. """
    with pytest.raises(ValueError) as exc_info:
        trait_db.search_traits(database, entity_id=person.entity_id,
                               numval_min=40, numval_max=30)
    error_msg = six.text_type(exc_info.value)
    assert "invalid range" in error_msg


def test_search_numval_unset(database, person, numvals):
    """ searching for numval=None returns explicitly unset traits. """
    results = list(trait_db.search_traits(database,
                                          entity_id=person.entity_id,
                                          numval=None))
    assert len(results) == 1


@pytest.fixture
def strvals(database, person, set_traits):
    return set_traits(
        person,
        a={'strval': "Hello, World!"},
        b={'strval': "example text"},
        c={'strval': "wildcard chars: % * ? _"},
        d={},
    )


def test_search_strval_unset(database, person, strvals):
    """ searching for strval=None returns explicitly unset trait values. """
    results = list(trait_db.search_traits(database,
                                          entity_id=person.entity_id,
                                          strval=None))
    assert len(results) == 1


def test_search_strval_exact(database, person, strvals):
    results = list(
        trait_db.search_traits(
            database,
            entity_id=person.entity_id,
            strval="example text",
        ),
    )
    assert len(results) == 1


@pytest.mark.parametrize(
    "pattern, hits",
    [
        ("example *", 1),
        ("example %", 0),
        ("example ???t", 1),
        ("example ___t", 0),
    ],
)
def test_search_strval_wildcard(database, person, strvals,
                                pattern, hits):
    results = list(trait_db.search_traits(database,
                                          entity_id=person.entity_id,
                                          strval_like=pattern))
    assert len(results) == hits


@pytest.mark.parametrize(
    "pattern, hits",
    [
        ("* chars: % \\* \\? _", 1),
        ("* chars: % \\* \\? x", 0),
    ],
)
def test_search_strval_escape(database, person, strvals,
                              pattern, hits):
    results = list(trait_db.search_traits(database,
                                          entity_id=person.entity_id,
                                          strval_like=pattern))
    assert len(results) == hits


@pytest.mark.parametrize(
    "pattern, hits",
    [
        ("Hello, W*", 1),
        ("hello, w*", 0),
    ],
)
def test_search_strval_case_sensitive(database, person, strvals,
                                      pattern, hits):
    results = list(trait_db.search_traits(database,
                                          entity_id=person.entity_id,
                                          strval_like=pattern))
    assert len(results) == hits


@pytest.mark.parametrize(
    "pattern, hits",
    [
        ("Hello, W*", 1),
        ("hello, w*", 1),
    ],
)
def test_search_strval_case_insensitive(database, person, strvals,
                                        pattern, hits):
    results = list(trait_db.search_traits(database,
                                          entity_id=person.entity_id,
                                          strval_ilike=pattern))
    assert len(results) == hits


#
# delete tests
#


def test_delete_code(database, person, set_traits):
    set_traits(person, a={}, b={}, c={})
    to_delete = (set_traits.a, set_traits.b)
    results = list(trait_db.delete_traits(database,
                                          entity_id=person.entity_id,
                                          code=to_delete))
    assert [r['code'] for r in results] == [int(t) for t in to_delete]
    remaining = list(trait_db.search_traits(database,
                                            entity_id=person.entity_id))
    assert [r['code'] for r in remaining] == [int(set_traits.c)]


def test_delete_iter(database, person, set_traits):
    """ everything is deleted even if we don't iterate over the results. """
    set_traits(person, a={}, b={}, c={})
    trait_db.delete_traits(database, entity_id=person.entity_id)
    remaining = list(trait_db.search_traits(database,
                                            entity_id=person.entity_id))
    assert len(remaining) == 0


#
# Check that _prefix can't leak through to our _select()
#


def test_search_invalid_arg(database, person):
    with pytest.raises(TypeError):
        trait_db.search_traits(database, entity_id=person.entity_id,
                               _prefix="foo")


def test_delete_invalid_arg(database, person):
    with pytest.raises(TypeError):
        trait_db.delete_traits(database, entity_id=person.entity_id,
                               _prefix="foo")


def test_get_invalid_arg(database, person, trait_a):
    with pytest.raises(TypeError):
        trait_db.get_trait(database, person.entity_id, trait_a,
                           _prefix="foo")
