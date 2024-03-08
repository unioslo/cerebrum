#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Basic tests for Cerebrum.Entity.EntityExternalId. """
import pytest


@pytest.fixture
def Entity(entity_module):
    return getattr(entity_module, 'EntityExternalId')


@pytest.fixture
def IdType(constant_module):
    return getattr(constant_module, '_EntityExternalIdCode')


@pytest.fixture
def id_num(IdType, entity_type):
    code = IdType('1eeabd6245bcdbab',
                  entity_type=entity_type,
                  description='id number')
    code.insert()
    return code


@pytest.fixture
def id_str(IdType, entity_type):
    code = IdType('cab2e1ddcdfdd79f',
                  entity_type=entity_type,
                  description='id string')
    code.insert()
    return code


@pytest.fixture
def entity_obj(database, Entity):
    return Entity(database)


@pytest.fixture
def entity(entity_obj, entity_type):
    entity_obj.populate(entity_type)
    entity_obj.write_db()
    return entity_obj


@pytest.fixture
def entities(
        Entity, database, entity_type, system_a, system_b, id_str,
        id_num):
    data = {}
    i = 0
    entity = Entity(database)

    for n in range(3):
        entity.populate(entity_type)
        entity.write_db()
        data[entity.entity_id] = dict()
        entity.clear()

    for eid in data:
        for sys in system_a, system_b:
            entity.find(eid)
            entity.affect_external_id(sys, id_str, id_num)
            data[eid][sys] = dict()
            for id_type in id_str, id_num:
                entity.populate_external_id(sys, id_type, str(i))
                data[eid][sys][id_type] = str(i)
                i += 1
            entity.write_db()
            entity.clear()

    # data = {<entity_id>: {<source>: {<id_type>: <value>,
    #                                  ..., },
    #                       ..., },
    #         ..., }
    return data


def test_get_external_id(entity_obj, entities):
    for e_id, ext_ids in entities.items():
        num_ids = len([id_type for sys in ext_ids for id_type in ext_ids[sys]])

        entity_obj.find(e_id)
        assert len(entity_obj.get_external_id()) == num_ids

        for sys in ext_ids:
            result = entity_obj.get_external_id(source_system=sys)
            assert len(result) == len(ext_ids[sys])
        entity_obj.clear()


def test_affect_source_error(entity, system_a, id_num):
    with pytest.raises(ValueError):
        entity.populate_external_id(system_a, id_num, '10')


def test_affect_wrong_source_error(entity, system_a, system_b, id_num):
    entity.affect_external_id(system_a, id_num)
    with pytest.raises(ValueError):
        entity.populate_external_id(system_b, id_num, '10')


def test_populate_extid(entity, system_a, id_num, id_str):
    entity.affect_external_id(system_a, id_num, id_str)
    entity.populate_external_id(system_a, id_num, '10')
    entity.populate_external_id(system_a, id_str, 'ten')
    entity.write_db()
    results = [r['external_id'] for r in entity.get_external_id()]
    assert len(results) == 2
    for val in ['10', 'ten']:
        assert val in results


def test_populate_affect(entity, system_a, id_num, id_str):
    entity.affect_external_id(system_a, id_num)
    entity.populate_external_id(system_a, id_num, '10')
    entity.populate_external_id(system_a, id_str, 'ten')
    entity.write_db()
    results = entity.get_external_id()
    assert len(results) == 1
    assert results[0]['external_id'] == '10'
    assert results[0]['id_type'] == id_num


def test_populate_clear(entity, system_a, system_b, id_num, id_str):
    entity_id = entity.entity_id
    entity.affect_external_id(system_a, id_num)
    entity.populate_external_id(system_a, id_num, '10')
    entity.clear()

    entity.find(entity_id)
    entity.affect_external_id(system_b, id_str)
    entity.populate_external_id(system_b, id_str, 'ten')
    entity.write_db()
    assert len(entity.get_external_id(source_system=system_a)) == 0
    assert len(entity.get_external_id(source_system=system_b)) == 1


def test_populate_update(entity, system_a, id_num, id_str):
    entity_id = entity.entity_id
    entity.affect_external_id(system_a, id_num, id_str)
    entity.populate_external_id(system_a, id_num, '10')
    entity.write_db()
    entity.clear()

    entity.find(entity_id)
    entity.affect_external_id(system_a, id_num, id_str)
    entity.populate_external_id(system_a, id_str, 'ten')
    entity.write_db()

    # Update should have removed id_num
    results = entity.get_external_id()
    assert len(results) == 1
    assert results[0]['id_type'] == id_str
    assert results[0]['external_id'] == 'ten'


def test_find_by_id(entity_obj, entities):
    for e_id, ext_id in entities.items():
        for sys, id_types in ext_id.items():
            for id_type, value in id_types.items():
                entity_obj.find_by_external_id(id_type, value,
                                               source_system=sys)
                assert entity_obj.entity_id == e_id
                entity_obj.clear()


def test_find_by_id_not_found(entity, system_a, id_str):
    from Cerebrum.Errors import NotFoundError

    with pytest.raises(NotFoundError):
        entity.find_by_external_id(id_str, 'ten')


def test_search_external_ids(entity_obj, entities):
    all_systems = set()
    all_id_types = set()
    all_id_pairs = []
    for e_id, ext_id in entities.items():
        id_pairs = []
        for sys, id_types in ext_id.items():
            all_systems.add(sys)
            for id_type, value in id_types.items():
                all_id_types.add(id_type)
                id_pairs.append((int(sys), int(id_type), value))
        all_id_pairs.extend(id_pairs)

        # Search by entity_id
        results = entity_obj.search_external_ids(entity_id=e_id)
        assert len(results) == len(id_pairs)

        fetched_pairs = [
            (int(r['source_system']), int(r['id_type']), r['external_id'])
            for r in results]
        for pair in id_pairs:
            assert pair in fetched_pairs

    # Search by systems and id types
    all_results = entity_obj.search_external_ids(source_system=all_systems,
                                                 id_type=all_id_types)
    assert len(all_results) == len(all_id_pairs)
    all_fetched_pairs = [
        (int(r['source_system']), int(r['id_type']), r['external_id'])
        for r in all_results]
    for pair in all_id_pairs:
        assert pair in all_fetched_pairs
