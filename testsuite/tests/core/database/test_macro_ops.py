# -*- coding: utf-8 -*-
"""
Tests for :mod:`Cerebrum.database.macros` default macro implementations.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

from Cerebrum.database import macros


@pytest.fixture
def config():
    return type(
        str('cereconf_mock'),
        (object,),
        {
            'STR_ATTR': 'asd',
            'INT_ATTR': 10,
        },
    )()


@pytest.fixture
def entity_type_cls(constant_module):
    return getattr(constant_module, '_EntityTypeCode')


@pytest.fixture
def constants(constant_module, entity_type_cls):
    base = getattr(constant_module, 'ConstantsBase')

    class ConstantContainer(base):
        entity_foo = entity_type_cls('4620a2402a8db1c3', description='foo')
        entity_bar = entity_type_cls('da0e1bf8bd56dcf7', description='bar')

    ConstantContainer.entity_foo.insert()

    return ConstantContainer()


@pytest.fixture
def context(config, constants):
    return {
        'config': config,
        'constants': constants,
    }


def test_op_table(context):
    schema = 'default'
    name = 'foo'
    result = macros.op_table(schema=schema, name=name, context=context)
    assert result == name


def test_op_now(context):
    result = macros.op_now(context=context)
    assert result == 'CURRENT_TIMESTAMP'


def test_op_get_config(context, config):
    expect = "'{}'".format(config.STR_ATTR)
    result = macros.op_get_config(var="STR_ATTR", context=context)
    assert result == expect


def test_op_get_config_missing_attr(context, config):
    with pytest.raises(ValueError, match="no config attribute"):
        macros.op_get_config(var="MISSING_ATTR", context=context)


def test_op_get_config_invalid_type(context, config):
    with pytest.raises(ValueError, match="invalid config value"):
        macros.op_get_config(var="INT_ATTR", context=context)


def test_op_get_constant(context, constants):
    name = 'entity_foo'
    expect = str(int(getattr(constants, name)))
    result = macros.op_get_constant(name=name, context=context)
    assert result == expect


def test_op_get_constant_missing_db(context):
    name = 'entity_bar'
    with pytest.raises(ValueError, match="invalid constant"):
        macros.op_get_constant(name=name, context=context)


def test_op_get_constant_missing_attr(context):
    name = 'please_please_do_not_exist_attr'
    with pytest.raises(ValueError, match="no constant"):
        macros.op_get_constant(name=name, context=context)


def test_boolean_deprecated(context):
    with pytest.deprecated_call():
        assert macros.op_boolean(context=context) == ""


def test_op_from_dual_default(context):
    assert macros.op_from_dual(context=context) == ""


def test_op_sequence_stub(context):
    with pytest.raises(ValueError, match="Invalid sequence operation"):
        macros.op_sequence("cerebrum", "foo", "nextval", context=context)


def test_op_sequence_start_deprecated(context):
    with pytest.deprecated_call():
        macros.op_sequence_start(value=3, context=context) == "START WITH 3"
