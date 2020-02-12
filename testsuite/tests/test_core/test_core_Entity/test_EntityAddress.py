#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Basic tests for Cerebrum.Entity.EntityAddress. """
import pytest


@pytest.fixture
def Entity(entity_module):
    return getattr(entity_module, 'EntityAddress')


@pytest.fixture
def AddrType(constant_module):
    return getattr(constant_module, '_AddressCode')


@pytest.fixture
def Country(constant_module):
    return getattr(constant_module, '_CountryCode')


@pytest.fixture
def country_no(Country):
    code = Country(
        '6da3fcb54ec8bc4c', country='NO', phone_prefix='47', description='NO')
    code.insert()
    return code


@pytest.fixture
def addr_work(AddrType):
    code = AddrType('46e73abcf1eeaf31', description='addr foo')
    code.insert()
    return code


@pytest.fixture
def addr_home(AddrType):
    code = AddrType('ea4eda57da2d42b4', description='addr bar')
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
def addr_data(country_no):
    data = [{'p_o_box': '313',
             'address_text': 'Apalveien 111',
             'city': 'Andebu',
             'postal_number': '3158',
             'country': country_no, },
            {'p_o_box': None,
             'address_text': 'Slottsplassen 1',
             'city': 'Oslo',
             'postal_number': '0010',
             'country': country_no, },
            {'p_o_box': '1072',
             'city': 'Oslo',
             'postal_number': '0316',
             'country': country_no, }, ]
    return data


def test_get_addr_info(entity, system_a, system_b, addr_home, addr_work):
    value = 'd8c7ec4fbbfb5c09'
    entity.add_entity_address(system_a, addr_home, city=value)
    entity.add_entity_address(system_a, addr_work, city='dd0c9da00a739cfd')
    entity.add_entity_address(system_b, addr_home, city='81bbddfa3cca7d85')

    assert len(entity.get_entity_address(system_a)) == 2
    result = entity.get_entity_address(system_a, addr_home)
    assert len(result) == 1
    assert result[0]['entity_id'] == entity.entity_id
    assert result[0]['source_system'] == system_a
    assert result[0]['address_type'] == addr_home
    assert result[0]['city'] == value
    assert result[0]['country'] is None


def test_addr_fields(entity, system_a, addr_work, country_no, addr_data):
    data = {'p_o_box': '313',
            'address_text': 'Apalveien 111',
            'city': 'Andebu',
            'postal_number': '3158',
            'country': country_no, }

    entity.add_entity_address(system_a, addr_work, **data)
    result = entity.get_entity_address(system_a, addr_work)
    assert len(result) == 1
    for field in data:
        assert result[0][field] == data[field]


def test_delete_addr_info(entity, system_a, addr_home, addr_work):
    entity.add_entity_address(system_a, addr_home, city='oslo')
    entity.add_entity_address(system_a, addr_work, city='rjukan')
    assert len(entity.get_entity_address()) == 2
    entity.delete_entity_address(system_a, addr_home)
    assert len(entity.get_entity_address()) == 1
    entity.delete_entity_address(system_a, addr_work)
    assert len(entity.get_entity_address()) == 0


def test_populate_addr_info(entity, system_a, addr_home, addr_work):
    entity.populate_address(system_a, addr_home, city='berlin')
    entity.populate_address(system_a, addr_work, city='paris')
    assert len(entity.get_entity_address(system_a)) == 0
    entity.write_db()
    assert len(entity.get_entity_address(system_a)) == 2


def test_populate_source_error(entity, system_a, system_b):
    entity.populate_address(system_a)  # Affect
    with pytest.raises(ValueError):
        entity.populate_address(system_b)


def test_list_addr_info(
        entity_obj, entity_type, system_a, addr_home, addr_data):
    data = dict()
    for addr in addr_data:
        entity_obj.populate(entity_type)
        entity_obj.populate_address(system_a, addr_home, **addr)
        entity_obj.write_db()
        data[entity_obj.entity_id] = addr
        entity_obj.clear()

    for eid, addr in data.items():
        found = entity_obj.list_entity_addresses(entity_id=eid)
        assert len(found) == 1
        for field in addr:
            assert found[0][field] == addr[field]

    results = entity_obj.list_entity_addresses(source_system=system_a,
                                               address_type=addr_home)
    assert len(results) == len(data)


def test_delete_entity_with_addr(entity, system_a, addr_home):
    from Cerebrum.Errors import NotFoundError
    entity_id = entity.entity_id
    entity.add_entity_address(system_a, addr_home, city='foo')

    entity.delete()
    entity.clear()

    assert len(entity.list_entity_addresses(entity_id=entity_id)) == 0
    with pytest.raises(NotFoundError):
        entity.find(entity_id)
