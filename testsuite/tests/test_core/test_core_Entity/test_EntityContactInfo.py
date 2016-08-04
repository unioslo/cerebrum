#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Basic tests for Cerebrum.Entity.EntityContactInfo. """
import pytest


@pytest.fixture
def Entity(entity_module):
    return getattr(entity_module, 'EntityContactInfo')


@pytest.fixture
def InfoType(constant_module):
    return getattr(constant_module, '_ContactInfoCode')


@pytest.fixture
def contact_foo(InfoType):
    code = InfoType('c08af2f8fce13999', description='contact foo')
    code.insert()
    return code


@pytest.fixture
def contact_bar(InfoType):
    code = InfoType('e19dd9bced236aee', description='contact bar')
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


def test_get_contact_info(
        entity, system_a, system_b, contact_foo, contact_bar):
    value = 'd8c7ec4fbbfb5c09'
    entity.add_contact_info(system_a, contact_foo, value)
    entity.add_contact_info(system_a, contact_bar, 'dd0c9da00a739cfd')
    entity.add_contact_info(system_b, contact_foo, '81bbddfa3cca7d85')
    entity.add_contact_info(system_b, contact_bar, 'bbf1ddbce9a4de3d')

    assert len(entity.get_contact_info(system_b)) == 2
    result = entity.get_contact_info(system_a, contact_foo)
    assert len(result) == 1
    assert result[0]['entity_id'] == entity.entity_id
    assert result[0]['source_system'] == system_a
    assert result[0]['contact_type'] == contact_foo
    assert result[0]['contact_value'] == value
    assert result[0]['contact_alias'] is None
    assert result[0]['description'] is None


def test_contact_info_description(entity, system_a, contact_foo):
    desc = 'do not contact me'
    entity.add_contact_info(system_a, contact_foo, 'foo', description=desc)

    result = entity.get_contact_info(system_a, contact_foo)
    assert len(result) == 1
    assert result[0]['description'] == desc


def test_contact_info_alias(entity, system_a, contact_foo):
    alias = 'some alias'
    entity.add_contact_info(system_a, contact_foo, 'foo', alias=alias)

    result = entity.get_contact_info(system_a, contact_foo)
    assert len(result) == 1
    assert result[0]['contact_alias'] == alias


def test_contact_info_pref(entity, system_a, contact_foo, contact_bar):
    entity.add_contact_info(system_a, contact_foo, 'x', pref=20)
    entity.add_contact_info(system_a, contact_foo, 'y', pref=30)
    entity.add_contact_info(system_a, contact_bar, 'z', pref=10)

    result = entity.get_contact_info(system_a)
    assert len(result) == 3
    # Check order
    assert result[0]['contact_value'] == 'z'
    assert result[1]['contact_value'] == 'x'
    assert result[2]['contact_value'] == 'y'


def test_delete_contact_info(entity, system_a, contact_foo, contact_bar):
    entity.add_contact_info(system_a, contact_foo, 'x', pref=5)
    entity.add_contact_info(system_a, contact_foo, 'x', pref=10)
    entity.add_contact_info(system_a, contact_bar, 'y')
    assert len(entity.get_contact_info()) == 3
    entity.delete_contact_info(system_a, contact_foo)
    assert len(entity.get_contact_info()) == 1
    entity.delete_contact_info(system_a, contact_bar)
    assert len(entity.get_contact_info()) == 0


def test_delete_contact_by_pref(entity, system_a, contact_foo, contact_bar):
    entity.add_contact_info(system_a, contact_foo, 'x', pref=5)
    entity.add_contact_info(system_a, contact_foo, 'y', pref=10)
    entity.add_contact_info(system_a, contact_bar, 'z', pref=10)
    assert len(entity.get_contact_info()) == 3
    entity.delete_contact_info(system_a, contact_foo, pref=10)
    result = entity.get_contact_info()
    assert len(result) == 2
    assert result[0]['contact_value'] == 'x'
    assert result[1]['contact_value'] == 'z'


def test_populate_contact_info(entity, system_a, contact_foo):
    entity.populate_contact_info(system_a, contact_foo, 'foo', 10)
    entity.populate_contact_info(system_a, contact_foo, 'bar', 20)
    assert len(entity.get_contact_info(system_a, contact_foo)) == 0
    entity.write_db()
    assert len(entity.get_contact_info(system_a, contact_foo)) == 2


def test_populate_source_error(entity, system_a, system_b):
    entity.populate_contact_info(system_a)  # Affect
    with pytest.raises(ValueError):
        entity.populate_contact_info(system_b)


def test_populate_clear(entity, system_a, system_b, contact_foo):
    entity_id = entity.entity_id
    entity.populate_contact_info(system_a, contact_foo, 'value')
    entity.clear()

    entity.find(entity_id)
    entity.populate_contact_info(system_b)
    entity.write_db()
    assert len(entity.get_contact_info()) == 0


def test_list_contact_info(entity_obj, entity_type, system_a, contact_foo):
    data = ({'value': 'foo', }, {'value': 'bar'}, {'value': 'baz'})

    for ent in data:
        entity_obj.populate(entity_type)
        entity_obj.populate_contact_info(system_a, contact_foo, ent['value'])
        entity_obj.write_db()
        ent['entity_id'] = entity_obj.entity_id
        entity_obj.clear()

    for ent in data:
        found = entity_obj.list_contact_info(entity_id=ent['entity_id'])
        assert len(found) == 1
        assert found[0]['contact_value'] == ent['value']

    results = entity_obj.list_contact_info(source_system=system_a,
                                           contact_type=contact_foo)
    assert len(results) == len(data)
    assert all(d['value'] in [r['contact_value'] for r in results]
               for d in data)


def test_delete_entity_with_contact_info(entity, system_a, contact_foo):
    from Cerebrum.Errors import NotFoundError
    entity_id = entity.entity_id
    entity.add_contact_info(system_a, contact_foo, 'foo')

    entity.delete()
    entity.clear()

    assert len(entity.list_contact_info(entity_id=entity_id)) == 0
    with pytest.raises(NotFoundError):
        entity.find(entity_id)


def test_sort_contact_info(entity, contact_foo, contact_bar, system_a,
                           system_b):
    entity.add_contact_info(system_a, contact_foo, 'w', pref=2)
    entity.add_contact_info(system_b, contact_foo, 'x', pref=4)
    entity.add_contact_info(system_a, contact_bar, 'y', pref=3)
    entity.add_contact_info(system_b, contact_foo, 'z', pref=1)
    contacts = entity.get_contact_info()

    spec = []
    result = entity.sort_contact_info(spec, contacts)
    assert len(result) == 0

    spec = [(system_b, contact_foo), (system_a, contact_foo)]
    result = entity.sort_contact_info(spec, contacts)
    assert len(result) == 3
    assert result[0]['source_system'] == system_b
    assert result[0]['contact_pref'] == 1
    assert result[2]['source_system'] == system_a

    spec = [(None, contact_bar), (system_b, contact_foo)]
    result = entity.sort_contact_info(spec, contacts)
    assert len(result) == 3
    assert (result[0]['source_system'] == system_a and
            result[0]['contact_type'] == contact_bar)
    assert (result[1]['contact_pref'] == 1)

    spec = [(system_b, None)]
    result = entity.sort_contact_info(spec, contacts)
    assert all(map(lambda x: x['source_system'] == system_b, result))
    assert len(result) == 2
    assert result[0]['contact_pref'] == 1

    spec = [(None, None)]
    result = entity.sort_contact_info(spec, contacts)
    assert len(result) == 4
    assert result[0]['contact_pref'] == 1
