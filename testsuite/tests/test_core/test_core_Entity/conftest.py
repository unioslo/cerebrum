#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Common fixtures for test_core_Entity. """
import pytest


@pytest.fixture
def database(database):
    u""" Database with cl_init set. """
    database.cl_init(change_program='test_core_Entity')
    return database


@pytest.fixture
def Spread(constant_module):
    return getattr(constant_module, '_SpreadCode')


@pytest.fixture
def Language(constant_module):
    return getattr(constant_module, '_LanguageCode')


@pytest.fixture
def EntityType(constant_module):
    return getattr(constant_module, '_EntityTypeCode')


@pytest.fixture
def entity_type(EntityType):
    code = EntityType('dfff34bdd3fde7da', description='Test type')
    code.insert()
    return code


@pytest.fixture
def entity_type_alt(EntityType):
    code = EntityType('8ebc1ddbacaccb2a', description='Second test type')
    code.insert()
    return code


@pytest.fixture
def System(constant_module):
    return getattr(constant_module, '_AuthoritativeSystemCode')


@pytest.fixture
def system_a(System):
    code = System('daed7dff718fac8a', description='System A')
    code.insert()
    return code


@pytest.fixture
def system_b(System):
    code = System('93a48f4cc4dfbf7b', description='System B')
    code.insert()
    return code


@pytest.fixture
def languages(Language):
    u""" A tuple with three language constants. """
    langs = tuple(
        (Language('bf3b7cdaa86cea2d', description='javascript'),
         Language('1fdeabb751e6770d', description='powershell'),
         Language('d6d03f2e3c3ebf45', description='visual basic')))
    for lang in langs:
        lang.insert()
    return langs


@pytest.fixture
def entity_module():
    from Cerebrum import Entity as module
    return module
