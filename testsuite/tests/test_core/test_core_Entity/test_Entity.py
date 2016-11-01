#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Basic tests for Cerebrum.Entity.Entity. """
import pytest


@pytest.fixture(params=['Entity',
                        'EntitySpread',
                        'EntityName',
                        'EntityNameWithLanguage',
                        'EntityContactInfo',
                        'EntityAddress',
                        'EntityQuarantine',
                        'EntityExternalId'])
def Entity(request, entity_module):
    u""" Branch and test each subtype of Entity. """
    return getattr(entity_module, request.param)


@pytest.fixture
def entity(database, Entity, entity_type):
    entity = Entity(database)
    entity.populate(entity_type)
    entity.write_db()
    return entity


def test_populate_entity(database, Entity, entity_type):
    entity = Entity(database)
    entity.populate(entity_type)
    assert entity.entity_type == entity_type


def test_populate_altered_entity(database, Entity, entity_type):
    entity = Entity(database)
    entity.populate(entity_type)
    with pytest.raises(RuntimeError):
        entity.populate(entity_type)


def test_write_db(database, Entity, entity_type):
    entity = Entity(database)
    entity.populate(entity_type)
    entity.write_db()
    assert entity.entity_id > -1


def test_comparison(database, Entity, entity_type):
    a_1, a_2, b = Entity(database), Entity(database), Entity(database)
    for ent in a_1, b:
        ent.populate(entity_type)
        ent.write_db()
    a_2.find(a_1.entity_id)
    assert a_1 == a_2
    assert a_2 == a_1
    assert b != a_1
    assert b != a_2
    assert a_1 != b
    assert a_2 != b


def test_clear(entity):
    assert entity.entity_id > -1
    entity.clear()
    assert not hasattr(entity, 'entity_id')


def test_find_by_id(entity):
    entity_id = entity.entity_id
    entity.clear()
    entity.find(entity_id)
    assert entity.entity_id == entity_id


def test_find_non_exising(entity):
    from Cerebrum.Errors import NotFoundError
    with pytest.raises(NotFoundError):
        entity.find(-1)


def test_delete(entity):
    from Cerebrum.Errors import NotFoundError
    entity_id = entity.entity_id
    entity.delete()
    entity.clear()
    with pytest.raises(NotFoundError):
        entity.find(entity_id)


def test_list_all_with_type(database, Entity, entity_type, entity_type_alt):
    entity = Entity(database)
    types = [entity_type, entity_type, entity_type, entity_type_alt]
    ids = set()
    for t in types:
        entity.populate(t)
        entity.write_db()
        if t == entity_type:
            ids.add(entity.entity_id)
        entity.clear()
    result = entity.list_all_with_type(entity_type)
    assert len(result) == len(ids)
    # Check that each id in ids is in the results
    assert all(entity_id in {r['entity_id'] for r in result}
               for entity_id in ids)


def test_get_subclassed_object(database, factory, Entity, entity_type):
    from Cerebrum.Entity import Entity as BaseEntity

    if Entity == BaseEntity:
        pytest.skip("Cannot test subclassed object with base class")

    # patch class into factory class cache
    factory_name = 'e3dc9cb2d58bdbda'
    factory.class_cache[factory_name] = Entity
    factory.type_component_map[str(entity_type)] = factory_name

    # Make entity of entity_type
    base = BaseEntity(database)
    base.populate(entity_type)
    base.write_db()

    # test
    entity = base.get_subclassed_object()
    assert type(entity) != type(base)
    assert type(entity) == Entity
