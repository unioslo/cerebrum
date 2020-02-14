# -*- coding: utf-8 -*-
"""
tests for Cerebrum.database.portability operator implementations.
"""
import pytest

from Cerebrum.database import macros


@pytest.fixture
def config():
    return type('cereconf_mock', (object,), {
        'FOO': 'asd',
        'BAR': 'xyz',
    })()


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
    var = 'FOO'
    expect = "'{}'".format(config.FOO)
    result = macros.op_get_config(var=var, context=context)
    assert result == expect


def test_op_get_constant(context, constants):
    name = 'entity_foo'
    expect = str(int(getattr(constants, name)))
    result = macros.op_get_constant(name=name, context=context)
    assert result == expect


def test_op_get_constant_missing_db(context):
    name = 'entity_bar'
    with pytest.raises(ValueError, match='invalid constant'):
        macros.op_get_constant(name=name, context=context)


def test_op_get_constant_missing_attr(context):
    name = 'please_please_do_not_exist_attr'
    with pytest.raises(ValueError, match='no constant'):
        macros.op_get_constant(name=name, context=context)
