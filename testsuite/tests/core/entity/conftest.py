#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Common fixtures for base entities. """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import pytest


@pytest.fixture
def database(database):
    """ Database with cl_init set. """
    database.cl_init(change_program='test_core_Entity')
    return database


@pytest.fixture
def Spread(constant_module):  # noqa: N802
    # TODO: Get rid of this fixture
    return getattr(constant_module, '_SpreadCode')


@pytest.fixture
def EntityType(constant_module):  # noqa: N802
    # TODO: Get rid of this fixture
    return getattr(constant_module, '_EntityTypeCode')


@pytest.fixture
def entity_type(constant_creator, constant_module):
    return constant_creator(
        constant_module._EntityTypeCode,
        "dfff34bdd3fde7da",
        description="Test type",
    )


@pytest.fixture
def entity_type_alt(constant_creator, constant_module):
    return constant_creator(
        constant_module._EntityTypeCode,
        "8ebc1ddbacaccb2a",
        description="Second test type",
    )


@pytest.fixture
def system_a(constant_creator, constant_module):
    return constant_creator(
        constant_module._AuthoritativeSystemCode,
        "daed7dff718fac8a",
        description="System A",
    )


@pytest.fixture
def system_b(constant_creator, constant_module):
    return constant_creator(
        constant_module._AuthoritativeSystemCode,
        "93a48f4cc4dfbf7b",
        description="System B",
    )


@pytest.fixture
def lang_js(constant_creator, constant_module):
    return constant_creator(
        constant_module._LanguageCode,
        "bf3b7cdaa86cea2d",
        description="javascript",
    )


@pytest.fixture
def lang_ps(constant_creator, constant_module):
    return constant_creator(
        constant_module._LanguageCode,
        "1fdeabb751e6770d",
        description="powershell",
    )


@pytest.fixture
def lang_vb(constant_creator, constant_module):
    return constant_creator(
        constant_module._LanguageCode,
        "d6d03f2e3c3ebf45",
        description="visual basic",
    )


@pytest.fixture
def languages(lang_js, lang_ps, lang_vb):
    """ A tuple with three language constants. """
    return tuple((
        lang_js,
        lang_ps,
        lang_vb,
    ))


@pytest.fixture
def entity_module():
    # TODO: Get rid of this fixture
    from Cerebrum import Entity as module  # noqa: N813
    return module
