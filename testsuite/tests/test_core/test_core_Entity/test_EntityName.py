#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Basic tests for Cerebrum.Entity.EntityName. """
import pytest


@pytest.fixture
def EntityName(entity_module):
    return getattr(entity_module, 'EntityName')


@pytest.fixture
def EntitySpread(entity_module):
    return getattr(entity_module, 'EntitySpread')


@pytest.fixture
def ValueDomain(constant_module):
    return getattr(constant_module, '_ValueDomainCode')


@pytest.fixture
def domain_foo(ValueDomain):
    code = ValueDomain('6b314b12edf18a1a', description='test nametype foo')
    code.insert()
    return code


@pytest.fixture
def domain_bar(ValueDomain):
    code = ValueDomain('df2d9fa17fb16aaa', description='test nametype bar')
    code.insert()
    return code


@pytest.fixture
def entity_spread(Spread, entity_type):
    code = Spread('4dade2a5ca8cb4ce',
                  entity_type,
                  description='Test spread for entity_type')
    code.insert()
    return code


@pytest.fixture
def entity(database, EntityName, entity_type):
    ent = EntityName(database)
    ent.populate(entity_type)
    ent.write_db()
    return ent


def test_add_name(entity, domain_foo):
    entity.add_entity_name(domain_foo, 'foo')
    assert len(entity.get_names()) == 1


def test_add_name_only_one_domain(entity, domain_foo):
    from Cerebrum.Database import DatabaseError
    entity.add_entity_name(domain_foo, 'foo')
    with pytest.raises(DatabaseError):
        entity.add_entity_name(domain_foo, 'foo')


def test_add_name_unique(database, EntityName, entity_type, domain_foo):
    from Cerebrum.Database import DatabaseError
    obj = list()
    for n in range(2):
        o = EntityName(database)
        o.populate(entity_type)
        o.write_db()
        obj.append(o)

    obj[0].add_entity_name(domain_foo, 'foo')
    with pytest.raises(DatabaseError):
        obj[1].add_entity_name(domain_foo, 'foo')


def test_get_name(entity, domain_foo, domain_bar):
    entity.add_entity_name(domain_foo, 'foo')
    entity.add_entity_name(domain_bar, 'bar')
    assert entity.get_name(domain_foo) == 'foo'
    assert entity.get_name(domain_bar) == 'bar'


def test_get_name_missing(entity, domain_foo):
    from Cerebrum.Errors import NotFoundError
    with pytest.raises(NotFoundError):
        entity.get_name(domain_foo)


def test_get_names(entity, domain_foo, domain_bar):
    entity.add_entity_name(domain_foo, 'foo')
    entity.add_entity_name(domain_bar, 'bar')
    names = [r['name'] for r in entity.get_names()]
    assert len(names) == 2
    assert 'foo' in names
    assert 'bar' in names


def test_update_entity_name(entity, domain_foo):
    entity.add_entity_name(domain_foo, 'foo')
    entity.update_entity_name(domain_foo, 'not foo')
    assert entity.get_name(domain_foo) == 'not foo'


def test_delete_entity_name(entity, domain_foo, domain_bar):
    from Cerebrum.Errors import NotFoundError
    entity.add_entity_name(domain_foo, 'foo')
    entity.add_entity_name(domain_bar, 'bar')
    entity.delete_entity_name(domain_foo)
    assert entity.get_name(domain_bar) == 'bar'
    with pytest.raises(NotFoundError):
        entity.get_name(domain_foo)


def test_find_by_name(entity, domain_foo, domain_bar):
    entity_id = entity.entity_id
    entity.add_entity_name(domain_foo, 'foo')
    entity.add_entity_name(domain_bar, 'bar')
    entity.clear()
    entity.find_by_name('foo', domain_foo)
    assert entity.entity_id == entity_id


def test_find_by_name_missing(entity, domain_foo, domain_bar):
    from Cerebrum.Errors import NotFoundError
    entity.add_entity_name(domain_foo, 'foo')
    entity.clear()
    with pytest.raises(NotFoundError):
        entity.find_by_name('foo', domain_bar)


def test_list_names(database, EntityName, EntitySpread, domain_foo, domain_bar, entity_spread):
    class Ent(EntityName, EntitySpread):
        u""" TODO: This is a hack.

        EntityName should not depend on EntitySpread.
        """
        pass
    first = Ent(database)
    first.populate(entity_spread.entity_type)
    first.write_db()
    first.add_spread(entity_spread)
    first.add_entity_name(domain_foo, 'first foo')

    second = Ent(database)
    second.populate(entity_spread.entity_type)
    second.write_db()
    second.add_entity_name(domain_foo, 'second foo')
    second.add_entity_name(domain_bar, 'second bar')

    assert len(first.list_names(domain_bar)) == 1
    assert len(first.list_names(domain_foo, spreads=entity_spread)) == 1
    assert len(first.list_names(domain_bar, spreads=entity_spread)) == 0

    results = first.list_names(domain_foo)
    assert len(results) == 2
    assert all(name in results[0].dict()
               for name in ['entity_id', 'value_domain', 'entity_name'])
    assert all(
        row in results for row
        in [(long(first.entity_id), long(int(domain_foo)), 'first foo'),
            (long(second.entity_id), long(int(domain_foo)), 'second foo')])
