# -*- coding: utf-8 -*-
""" Tests for :mod:`Cerebrum.modules.ad_attributes.adattr_db` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import operator

import pytest

from Cerebrum import Errors
from Cerebrum import Entity
from Cerebrum.Constants import _EntityTypeCode, _SpreadCode
from Cerebrum.modules.ad_attributes import adattr_db
from Cerebrum.modules.ad_attributes import adattr_constants


ATTR_FOO = "attr-foo-e937af"
ATTR_BAR = "attr-bar-cafd5d"
ATTR_MULTI = "attr-multi-a770be"


SPREAD_FOO = "spread-foo-937a"
SPREAD_BAR = "spread-bar-afd5"


@pytest.fixture(autouse=True)
def _clear_ad_attr_code_cache():
    # As the _ADAttrCode isn't present in the core Constants module, it won't
    # get automatically cleared by our constant_module fixture.
    adattr_constants._ADAttrCode._cache = {}


@pytest.fixture
def ad_attr_foo(constant_creator):
    return constant_creator(
        adattr_constants._ADAttrCode,
        ATTR_FOO,
        description="Test attribute for {}".format(__name__),
        multivalued=False,
    )


@pytest.fixture
def ad_attr_bar(constant_creator):
    return constant_creator(
        adattr_constants._ADAttrCode,
        ATTR_BAR,
        description="Test attribute for {}".format(__name__),
        multivalued=False,
    )


@pytest.fixture
def ad_attr_multi(constant_creator):
    return constant_creator(
        adattr_constants._ADAttrCode,
        ATTR_MULTI,
        description="Multivalued test attribute for {}".format(__name__),
        multivalued=True,
    )


@pytest.fixture
def spread_foo(constant_creator, entity_type):
    return constant_creator(
        _SpreadCode,
        SPREAD_FOO,
        description="Test spread for {}".format(__name__),
        entity_type=entity_type,
    )


@pytest.fixture
def spread_bar(constant_creator, entity_type):
    return constant_creator(
        _SpreadCode,
        SPREAD_BAR,
        description="Test spread for {}".format(__name__),
        entity_type=entity_type,
    )


@pytest.fixture
def entity_type(constant_creator):
    return constant_creator(
        _EntityTypeCode,
        "test-entity-36af",
        description="Test entity type for {}".format(__name__),
    )


@pytest.fixture
def entity(database, entity_type):
    """ A simple AdAttributeCleanupMixin entity. """
    obj = Entity.Entity(database)
    obj.populate(entity_type)
    obj.write_db()
    return obj


def test_set_ad_attribute(database, entity, ad_attr_foo, spread_foo):
    result = adattr_db.set_ad_attribute(
        db=database,
        entity_id=entity.entity_id,
        spread_code=spread_foo,
        attr_code=ad_attr_foo,
        subattr_id=0,
        value="test-value",
    )
    assert dict(result) == {
        'entity_id': entity.entity_id,
        'spread_code': int(spread_foo),
        'attr_code': int(ad_attr_foo),
        'subattr_id': 0,
        'value': "test-value",
    }


def test_get_ad_attribute_hit(database, entity, ad_attr_foo, spread_foo):
    adattr_db.set_ad_attribute(
        db=database,
        entity_id=entity.entity_id,
        spread_code=spread_foo,
        attr_code=ad_attr_foo,
        subattr_id=0,
        value="test-value",
    )
    result = adattr_db.get_ad_attribute(
        db=database,
        entity_id=entity.entity_id,
        spread_code=spread_foo,
        attr_code=ad_attr_foo,
    )
    assert dict(result) == {
        'entity_id': entity.entity_id,
        'spread_code': int(spread_foo),
        'attr_code': int(ad_attr_foo),
        'subattr_id': 0,
        'value': "test-value",
    }


def test_get_ad_attribute_miss(database, entity, ad_attr_foo, spread_foo):
    with pytest.raises(Errors.NotFoundError):
        adattr_db.get_ad_attribute(
            db=database,
            entity_id=entity.entity_id,
            spread_code=spread_foo,
            attr_code=ad_attr_foo,
        )


def test_set_ad_attribute_invalid_subattr(database, entity, ad_attr_foo,
                                          spread_foo):
    with pytest.raises(ValueError):
        adattr_db.set_ad_attribute(
            db=database,
            entity_id=entity.entity_id,
            spread_code=spread_foo,
            attr_code=ad_attr_foo,
            subattr_id=1,
            value="test-value",
        )


def test_set_ad_attribute_update(database, entity, ad_attr_foo, spread_foo):
    adattr_db.set_ad_attribute(
        db=database,
        entity_id=entity.entity_id,
        spread_code=spread_foo,
        attr_code=ad_attr_foo,
        subattr_id=0,
        value="initial value",
    )
    adattr_db.set_ad_attribute(
        db=database,
        entity_id=entity.entity_id,
        spread_code=spread_foo,
        attr_code=ad_attr_foo,
        subattr_id=0,
        value="updated value",
    )

    # check that we got both subattrs
    result = adattr_db.get_ad_attribute(
        db=database,
        entity_id=entity.entity_id,
        spread_code=spread_foo,
        attr_code=ad_attr_foo,
    )
    assert result['value'] == "updated value"


def test_set_ad_attribute_multi(database, entity, ad_attr_multi, spread_foo):
    expected = []

    for subattr_id in (1, 0):
        # explicitly set subattr_id 1 before subattr_id 0
        value = "test-value-{}".format(subattr_id)
        adattr_db.set_ad_attribute(
            db=database,
            entity_id=entity.entity_id,
            spread_code=spread_foo,
            attr_code=ad_attr_multi,
            subattr_id=subattr_id,
            value=value,
        )
        expected.append({
            'entity_id': entity.entity_id,
            'spread_code': int(spread_foo),
            'attr_code': int(ad_attr_multi),
            'subattr_id': subattr_id,
            'value': value,
        })

    # we expect to get "identical" attributes sorted by subattr_id
    expected.sort(key=operator.itemgetter('subattr_id'))

    # check that we got both subattrs
    results = adattr_db.get_ad_attribute(
        db=database,
        entity_id=entity.entity_id,
        spread_code=spread_foo,
        attr_code=ad_attr_multi,
    )
    assert len(results) == 2
    assert [dict(r) for r in results] == expected


def test_set_ad_attribute_per_spread(database, entity, ad_attr_foo, spread_foo,
                                     spread_bar):
    for spread in (spread_foo, spread_bar):
        value = "test-value-{}".format(spread)
        adattr_db.set_ad_attribute(
            db=database,
            entity_id=entity.entity_id,
            spread_code=spread,
            attr_code=ad_attr_foo,
            subattr_id=0,
            value=value,
        )

    # check that we got both subattrs
    for spread in (spread_foo, spread_bar):
        result = adattr_db.get_ad_attribute(
            db=database,
            entity_id=entity.entity_id,
            spread_code=spread,
            attr_code=ad_attr_foo,
        )
        assert result['value'] == "test-value-{}".format(spread)


def test_search_ad_attribute(database, entity, spread_foo, ad_attr_foo,
                             ad_attr_bar):
    values = set()
    for attr_code in (ad_attr_foo, ad_attr_bar):
        value = "test-value-{}".format(attr_code)
        adattr_db.set_ad_attribute(
            db=database,
            entity_id=entity.entity_id,
            spread_code=spread_foo,
            attr_code=attr_code,
            subattr_id=0,
            value=value,
        )
        values.add(value)

    results = adattr_db.search_ad_attributes(database,
                                             entity_id=entity.entity_id)
    assert len(results) == len(values)
    assert set((r['value'] for r in results)) == values


def test_search_ad_attribute_limit(database, entity, spread_foo, ad_attr_foo,
                                   ad_attr_bar):
    for attr_code in (ad_attr_foo, ad_attr_bar):
        adattr_db.set_ad_attribute(
            db=database,
            entity_id=entity.entity_id,
            spread_code=spread_foo,
            attr_code=attr_code,
            subattr_id=0,
            value="limit-test",
        )

    results = adattr_db.search_ad_attributes(database,
                                             entity_id=entity.entity_id,
                                             limit=1)
    assert len(results) == 1
    assert results[0]['value'] == "limit-test"


def test_search_ad_attribute_pattern(database, entity, spread_foo, ad_attr_foo,
                                     ad_attr_bar):
    to_set = [(ad_attr_foo, "prefix VALUE"), (ad_attr_bar, "VALUE suffix")]
    for attr_code, value in to_set:
        adattr_db.set_ad_attribute(
            db=database,
            entity_id=entity.entity_id,
            spread_code=spread_foo,
            attr_code=attr_code,
            subattr_id=0,
            value=value,
        )

    results = adattr_db.search_ad_attributes(database,
                                             entity_id=entity.entity_id,
                                             value_ilike="value *")
    assert len(results) == 1
    assert results[0]['attr_code'] == ad_attr_bar


def test_delete_ad_attribute(database, entity, spread_foo, ad_attr_foo,
                             ad_attr_bar):
    for attr_code in (ad_attr_foo, ad_attr_bar):
        value = "test-value-{}".format(attr_code)
        adattr_db.set_ad_attribute(
            db=database,
            entity_id=entity.entity_id,
            spread_code=spread_foo,
            attr_code=attr_code,
            subattr_id=0,
            value=value,
        )

    results = adattr_db.delete_ad_attributes(database,
                                             entity_id=entity.entity_id,
                                             attr_code=ad_attr_foo)
    assert len(results) == 1
    assert dict(results[0]) == {
        'entity_id': entity.entity_id,
        'spread_code': int(spread_foo),
        'attr_code': int(ad_attr_foo),
        'subattr_id': 0,
        'value': "test-value-{}".format(ad_attr_foo),
    }

    remaining = adattr_db.search_ad_attributes(database,
                                               entity_id=entity.entity_id)
    assert len(remaining) == 1
    assert dict(remaining[0]) == {
        'entity_id': entity.entity_id,
        'spread_code': int(spread_foo),
        'attr_code': int(ad_attr_bar),
        'subattr_id': 0,
        'value': "test-value-{}".format(ad_attr_bar),
    }
