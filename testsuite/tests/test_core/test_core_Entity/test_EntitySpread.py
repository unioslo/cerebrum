#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Basic tests for Cerebrum.Entity.EntitySpread. """
import pytest


@pytest.fixture
def entity_spread(Spread, entity_type):
    code = Spread('f303846618175b16',
                  entity_type,
                  description='Test spread for entity_type')
    code.insert()
    return code


@pytest.fixture
def entity_spread_alt(Spread, entity_type):
    code = Spread('b36b563d6a4db0e5',
                  entity_type,
                  description='Second test spread for entity_type')
    code.insert()
    return code


@pytest.fixture
def Entity(entity_module):
    u""" Branch and test each subtype of Entity. """
    return getattr(entity_module, 'EntitySpread')


@pytest.fixture
def entity_obj(database, Entity):
    u""" An instance of Entity, with database. """
    return Entity(database)


@pytest.fixture
def entity_simple(entity_obj, entity_type):
    u""" entity_obj, but populated. """
    entity_obj.populate(entity_type)
    entity_obj.write_db()
    return entity_obj


@pytest.fixture
def entity(entity_simple, entity_spread, entity_spread_alt):
    u""" entity_simple, but with spreads. """
    entity_simple.add_spread(entity_spread)
    entity_simple.add_spread(entity_spread_alt)
    return entity_simple


@pytest.fixture
def entities(entity_obj, entity_type, entity_spread, entity_spread_alt):
    u""" Entity info on four entities with different sets of spreads. """
    entities = list()
    spread_dist = [
        (),
        (entity_spread, ),
        (entity_spread, entity_spread_alt, ),
        (entity_spread_alt, ), ]

    for spreads in spread_dist:
        try:
            entry = dict()
            entity_obj.populate(entity_type)
            entity_obj.write_db()
            for spread in spreads:
                entity_obj.add_spread(spread)
            entry = {
                'entity_id': entity_obj.entity_id,
                'entity_type': entity_obj.entity_type,
                'spreads': spreads, }
            entities.append(entry)
        except Exception:
            entity_obj._db.rollback()
            raise
        finally:
            entity_obj.clear()
    return entities


def test_delete_with_spread(entity):
    from Cerebrum.Errors import NotFoundError
    entity_id = entity.entity_id
    entity.delete()
    entity.clear()
    with pytest.raises(NotFoundError):
        entity.find(entity_id)


def test_get_spread(entity, entity_spread, entity_spread_alt):
    spreads = [row['spread'] for row in entity.get_spread()]
    assert all(int(spread) in spreads
               for spread in (entity_spread, entity_spread_alt))


def test_has_spread(entity_simple, entity_spread, entity_spread_alt):
    entity_simple.add_spread(entity_spread_alt)
    assert entity_simple.has_spread(entity_spread_alt)
    assert not entity_simple.has_spread(entity_spread)
    entity_simple.add_spread(entity_spread)
    assert entity_simple.has_spread(entity_spread)


def test_delete_spread(entity, entity_spread, entity_spread_alt):
    entity.delete_spread(entity_spread)
    assert not entity.has_spread(entity_spread)
    assert entity.has_spread(entity_spread_alt)


def test_list_spreads(entity, entity_type, entity_spread, entity_spread_alt):
    columns = ['spread_code', 'spread', 'description', 'entity_type',
               'entity_type_str']

    all_spreads = entity.list_spreads()
    assert len(all_spreads) >= len((entity_spread, entity_spread_alt))
    for col in columns:
        assert col in all_spreads[0].dict()

    # 'entity_spread' and 'entity_spread_alt' should be the only spreads that
    # apply to 'entity_type'
    entity_spreads = entity.list_spreads(entity_types=entity_type)
    assert len(entity_spreads) == len((entity_spread, entity_spread_alt))
    assert entity_spread.description in [r['description'] for r in
                                         entity_spreads]
    assert str(entity_spread_alt) in [r['spread'] for r in entity_spreads]


def test_list_all_with_spread(entity_obj, entities):
    spreads = {spread for ent in entities for spread in ent['spreads']}
    result = entity_obj.list_all_with_spread(spreads=spreads)

    result_ids = {r['entity_id'] for r in result}
    for entry in entities:
        if entry['spreads']:
            assert entry['entity_id'] in result_ids
        else:
            assert entry['entity_id'] not in result_ids


def test_list_entity_spreads(entity_obj, entities, entity_type):
    expected = [(long(ent['entity_id']), long(int(spread)))
                for ent in entities
                for spread in ent['spreads']]
    entity_types = {ent['entity_type'] for ent in entities}

    all_results = entity_obj.list_entity_spreads()
    assert len(all_results) >= len(expected)

    results = entity_obj.list_entity_spreads(entity_types=entity_types)
    assert list(tuple(r) for r in results) == expected
