# -*- coding: utf-8 -*-
""" Tests for :mod:`Cerebrum.modules.feide.service` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

from Cerebrum import Errors
from Cerebrum.Constants import _EntityTypeCode
from Cerebrum.modules.feide import service


FEIDE_SERVICE_ID = "af536afafc6dab7f"
FEIDE_SERVICE_NAME = "test-service-9c40ecda"


#
# FeideService tests
#


def test_feide_service_init(database):
    obj = service.FeideService(database)
    assert obj
    assert not obj.feide_id
    assert not obj.name


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("x", id="short"),
        pytest.param("x" * 128, id="long"),
        pytest.param("foo.BAR_01-9", id="legal-chars"),
        pytest.param(FEIDE_SERVICE_NAME, id="test-name"),
    ],
)
def test_feide_service_legal_name(database, name):
    obj = service.FeideService(database)
    assert not obj.illegal_name(name)


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("", id="empty"),
        pytest.param("x" * 129, id="too-long"),
        pytest.param("foo?BAR?01", id="illegal-chars"),
    ],
)
def test_feide_service_illegal_name(database, name):
    obj = service.FeideService(database)
    assert obj.illegal_name(name)


def test_feide_service_populate(database):
    obj = service.FeideService(database)
    obj.populate(FEIDE_SERVICE_ID, FEIDE_SERVICE_NAME)
    assert obj.feide_id == FEIDE_SERVICE_ID
    assert obj.name == FEIDE_SERVICE_NAME


@pytest.fixture
def feide_service(database):
    obj = service.FeideService(database)
    obj.populate(FEIDE_SERVICE_ID, FEIDE_SERVICE_NAME)
    obj.write_db()
    return obj


def test_feide_service_write_new(feide_service):
    assert feide_service.entity_id


def test_feide_service_find(database, feide_service):
    obj = service.FeideService(database)
    obj.find(feide_service.entity_id)
    assert obj.entity_id == feide_service.entity_id
    assert obj.feide_id == FEIDE_SERVICE_ID
    assert obj.name == FEIDE_SERVICE_NAME


def test_feide_service_find_by_name(database, feide_service):
    obj = service.FeideService(database)
    obj.find_by_name(FEIDE_SERVICE_NAME)
    assert obj.entity_id == feide_service.entity_id
    assert obj.feide_id == FEIDE_SERVICE_ID
    assert obj.name == FEIDE_SERVICE_NAME


def test_feide_service_clear(database, feide_service):
    obj = feide_service
    obj.clear()
    # the entity superclass actually removes the entity_id attribute
    assert not getattr(obj, "entity_id", None)
    assert not obj.feide_id
    assert not obj.name


def test_feide_service_reuse(database, feide_service):
    entity_id = int(feide_service.entity_id)

    obj = feide_service
    obj.clear()
    obj.find(entity_id)

    assert obj.entity_id == entity_id
    assert obj.feide_id == FEIDE_SERVICE_ID
    assert obj.name == FEIDE_SERVICE_NAME


def test_feide_service_write_update(feide_service):
    entity_id = int(feide_service.entity_id)
    obj = feide_service
    new_name = FEIDE_SERVICE_NAME + "-updated"
    new_id = FEIDE_SERVICE_ID + "-01"

    obj.feide_id = new_id
    obj.name = new_name
    obj.write_db()
    assert obj.feide_id == new_id
    assert obj.name == new_name

    obj.clear()
    obj.find(entity_id)
    assert obj.entity_id == entity_id
    assert obj.feide_id == new_id
    assert obj.name == new_name


def test_feide_service_search_feide_id(database, feide_service):
    # add a second service, to *not* include in results
    obj = service.FeideService(database)
    obj.populate(FEIDE_SERVICE_ID + "-02", FEIDE_SERVICE_NAME + "-alt")
    obj.write_db()

    results = list(obj.search(feide_id=feide_service.feide_id))
    assert len(results) == 1
    assert dict(results[0]) == {
        'service_id': feide_service.entity_id,
        'feide_id': feide_service.feide_id,
        'name': feide_service.name,
    }


def test_feide_service_search_name_pattern(database, feide_service):
    # add services
    a = service.FeideService(database)
    a.populate(FEIDE_SERVICE_ID + "-01", FEIDE_SERVICE_NAME + "-suffix")
    a.write_db()

    # add services
    b = service.FeideService(database)
    b.populate(FEIDE_SERVICE_ID + "-02", "prefix-" + FEIDE_SERVICE_NAME)
    b.write_db()

    pattern = FEIDE_SERVICE_NAME + "*"
    expected_ids = set((feide_service.entity_id, a.entity_id))

    results = list(a.search(name=pattern))
    assert len(results) == 2
    assert set(r['service_id'] for r in results) == expected_ids


def test_feide_service_write_noop(feide_service):
    entity_id = int(feide_service.entity_id)
    obj = feide_service

    obj.write_db()  # no change
    assert obj.entity_id == entity_id
    assert obj.feide_id == FEIDE_SERVICE_ID
    assert obj.name == FEIDE_SERVICE_NAME


def test_feide_service_delete(feide_service):
    # sanity check feide_service.search() result
    assert list(feide_service.search(feide_id=FEIDE_SERVICE_ID))

    feide_service.delete()
    assert not list(feide_service.search(feide_id=FEIDE_SERVICE_ID))


#
# FeideServiceAuthnLevelMixin tests
#


@pytest.fixture
def mock_type(constant_creator):
    return constant_creator(_EntityTypeCode, "mock-type-dcd4")


def test_feide_authn_level_init(database):
    assert service.FeideServiceAuthnLevelMixin(database)


def test_feide_authn_level_populate(database, mock_type):
    obj = service.FeideServiceAuthnLevelMixin(database)
    obj.populate(mock_type)
    assert obj.entity_type == mock_type


@pytest.fixture
def feide_authn_object_a(database, mock_type):
    obj = service.FeideServiceAuthnLevelMixin(database)
    obj.populate(mock_type)
    obj.write_db()
    return obj


@pytest.fixture
def feide_authn_object_b(database, mock_type):
    obj = service.FeideServiceAuthnLevelMixin(database)
    obj.populate(mock_type)
    obj.write_db()
    return obj


def test_feide_authn_level_find(database, feide_authn_object_a):
    entity_id = int(feide_authn_object_a.entity_id)

    obj = service.FeideServiceAuthnLevelMixin(database)
    obj.find(entity_id)
    assert obj.entity_id == entity_id


def test_feide_authn_level_clear(feide_authn_object_a):
    obj = feide_authn_object_a
    obj.clear()
    assert not getattr(obj, "entity_id", None)


def test_feide_authn_level_add_entity(feide_service,
                                      feide_authn_object_a):
    obj = feide_authn_object_a
    obj.add_authn_level(feide_service.entity_id, 1, entity_id=obj.entity_id)

    levels = list(
        obj.search_authn_level(service_id=feide_service.entity_id)
    )
    assert len(levels) == 1
    assert set(r['entity_id'] for r in levels) == set((obj.entity_id,))


@pytest.fixture
def authn_levels(feide_service, feide_authn_object_a, feide_authn_object_b):
    obj = feide_authn_object_a
    levels = [
        {
            'service_id': feide_service.entity_id,
            'level': 2,
            'entity_id': feide_authn_object_a.entity_id,
        },
        {
            'service_id': feide_service.entity_id,
            'level': 3,
            'entity_id': feide_authn_object_a.entity_id,
        },
    ]
    for kwargs in levels:
        obj.add_authn_level(**kwargs)
    return levels


def authn_level_sort_key(authn_level_dict):
    return (
        authn_level_dict.get('service_id'),
        authn_level_dict.get('level'),
        authn_level_dict.get('entity_id'),
    )


def test_feide_authn_level_remove_entity(database, feide_service,
                                         authn_levels):
    to_remove = authn_levels[0]
    expected = sorted(authn_levels[1:], key=authn_level_sort_key)

    # entity_id defaults to feide_authn_object_a:
    obj = service.FeideServiceAuthnLevelMixin(database)
    obj.remove_authn_level(**to_remove)
    results = sorted(
        (dict(r)
         for r in obj.search_authn_level(service_id=feide_service.entity_id)),
        key=authn_level_sort_key,
    )
    assert results == expected


def test_feide_auth_level_search_entity(database, feide_service, authn_levels):
    to_find = authn_levels[0]['entity_id']
    expected = sorted(
        (r for r in authn_levels if r['entity_id'] == to_find),
        key=authn_level_sort_key,
    )

    # entity_id defaults to feide_authn_object_a:
    obj = service.FeideServiceAuthnLevelMixin(database)
    results = sorted(
        (dict(r)
         for r in obj.search_authn_level(entity_id=to_find)),
        key=authn_level_sort_key,
    )
    assert results == expected


def test_feide_auth_level_search_service(database, feide_service,
                                         authn_levels):
    expected = sorted(
        (r for r in authn_levels
         if r['service_id'] == feide_service.entity_id),
        key=authn_level_sort_key,
    )

    # entity_id defaults to feide_authn_object_a:
    obj = service.FeideServiceAuthnLevelMixin(database)
    results = sorted(
        (dict(r)
         for r in obj.search_authn_level(service_id=feide_service.entity_id)),
        key=authn_level_sort_key,
    )
    assert results == expected


def test_feide_auth_level_search_level(database, feide_service, authn_levels):
    expected = sorted(
        (r for r in authn_levels
         if r['service_id'] == feide_service.entity_id and r['level'] == 2),
        key=authn_level_sort_key,
    )

    # entity_id defaults to feide_authn_object_a:
    obj = service.FeideServiceAuthnLevelMixin(database)
    results = sorted(
        (dict(r)
         for r in obj.search_authn_level(service_id=feide_service.entity_id,
                                         level=2)),
        key=authn_level_sort_key,
    )
    assert results == expected


def test_feide_auth_level_delete(database, feide_authn_object_a):
    entity_id = int(feide_authn_object_a.entity_id)
    feide_authn_object_a.delete()

    obj = service.FeideServiceAuthnLevelMixin(database)
    with pytest.raises(Errors.NotFoundError):
        obj.find(entity_id)


def test_feide_auth_level_delete_with_deps(database, feide_authn_object_a,
                                           authn_levels):
    entity_id = int(feide_authn_object_a.entity_id)
    feide_authn_object_a.delete()

    obj = service.FeideServiceAuthnLevelMixin(database)
    assert not list(obj.search_authn_level(entity_id=entity_id))


#
# FeideService / FeideServiceAuthnLevelMixin integration tests
#


def test_feide_service_delete_with_deps(database, feide_service, authn_levels):
    obj = service.FeideServiceAuthnLevelMixin(database)
    service_id = int(feide_service.entity_id)
    feide_service.delete()

    assert not list(obj.search_authn_level(service_id=service_id))
