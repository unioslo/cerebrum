#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Basic tests for Cerebrum.Entity.EntityNameWithLanguage. """
import pytest


@pytest.fixture
def Entity(entity_module):
    return getattr(entity_module, 'EntityNameWithLanguage')


@pytest.fixture
def NameType(constant_module):
    return getattr(constant_module, '_EntityNameCode')


@pytest.fixture
def name_foo(NameType):
    code = NameType('5f23ff37b95234ea', description='foo')
    code.insert()
    return code


@pytest.fixture
def name_bar(NameType):
    code = NameType('4cdb3dfcf7fec07b', description='bar')
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
def entities(entity_obj, entity_type, name_foo, name_bar, languages):
    u""" Entity info on four entities with different sets of spreads. """
    entities = list()

    name_dist = [
        (),
        ((name_foo, languages[0]), (name_foo, languages[1]), ),
        ((name_foo, languages[1]), (name_foo, languages[2]),
         (name_bar, languages[1]), ),
        ((name_bar, languages[2]), ), ]

    for name_list in name_dist:
        try:
            entry = dict()
            entity_obj.populate(entity_type)
            entity_obj.write_db()
            for name, lang in name_list:
                entity_obj.add_name_with_language(name, lang, lang.description)
            entry = {
                'entity_id': entity_obj.entity_id,
                'entity_type': entity_obj.entity_type,
                'names': name_list, }
            entities.append(entry)
        except:
            entity_obj._db.rollback()
            raise
        finally:
            entity_obj.clear()
    return entities


def test_add_name_with_language(entity, name_foo, languages):
    for num, lang in enumerate(languages):
        print num, str(lang), lang.description
        entity.add_name_with_language(name_foo, lang, lang.description)

    for num, lang in enumerate(languages):
        localized = entity.get_name_with_language(name_foo, lang)
        print num, localized
        assert len(localized) > 1
        assert localized == lang.description


def test_update_name_with_language(entity, name_foo, languages):
    for num, lang in enumerate(languages):
        num = num * 2
        print num, str(lang), lang.description
        entity.add_name_with_language(name_foo, lang, str(num))
        print num + 1, str(lang), lang.description
        entity.add_name_with_language(name_foo, lang, str(num + 1))

    for num, lang in enumerate(languages):
        # Only the last one should exist
        num = num * 2 + 1
        localized = entity.get_name_with_language(name_foo, lang)
        print num, localized
        assert localized == str(num)


def test_search_name_with_language(entity_obj, entities):
    names = [name for e in entities for name in e['names']]
    all_entity_names = entity_obj.search_name_with_language()
    assert len(all_entity_names) >= len(names)

    for ent in entities:
        found = entity_obj.search_name_with_language(
            entity_id=ent['entity_id'])
        assert len(found) == len(ent['names'])

    for name in names:
        matches = [e['entity_id'] for e in entities if name in e['names']]
        found = entity_obj.search_name_with_language(name_variant=name[0],
                                                     name_language=name[1])
        assert len(found) == len(matches)
        assert all(r['entity_id'] in matches for r in found)


def test_get_name_with_language(entity_obj, entities):
    for ent in entities:
        entity_obj.find(ent['entity_id'])
        for variant, lang in ent['names']:
            name = entity_obj.get_name_with_language(variant, lang)
            assert name == lang.description
        entity_obj.clear()


def test_get_name_with_language_missing(entity, name_foo, languages):
    from Cerebrum.Errors import NotFoundError
    name = entity.get_name_with_language(name_foo, languages[0], 'default')
    assert name == 'default'

    with pytest.raises(NotFoundError):
        entity.get_name_with_language(name_foo, languages[0])


def test_delete_name_with_language(entity, name_foo, languages):
    entity.add_name_with_language(name_foo, languages[0], 'f354c390af60ea7a')
    entity.delete_name_with_language(name_foo, languages[0])
    found = entity.get_name_with_language(name_foo, languages[0], 'default')
    assert found == 'default'


def test_delete_entity_with_localized_names(entity, name_foo, languages):
    from Cerebrum.Errors import NotFoundError
    entity_id = entity.entity_id
    for lang in languages:
        entity.add_name_with_language(name_foo, lang, lang.description)
    entity.delete()
    entity.clear()

    with pytest.raises(NotFoundError):
        entity.find(entity_id)
