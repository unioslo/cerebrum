# -*- coding: utf-8 -*-
"""
tests for Cerebrum.database.macros.MacroTable.
"""
import pytest

from Cerebrum.database import macros


def _simple_op_factory(expected_result):
    def op(*args, **kwargs):
        return expected_result
    return op


@pytest.fixture
def foo_op():
    return _simple_op_factory('foo_result')


@pytest.fixture
def bar_op():
    return _simple_op_factory('bar_result')


@pytest.fixture
def table(foo_op, bar_op):
    table = macros.MacroTable({'foo': foo_op,
                               'bar': bar_op})
    return table


def test_empty_init():
    # is this test too fine grained?
    table = macros.MacroTable()
    assert isinstance(table, macros.MacroTable)


def test_nonempty_init(table):
    # fixture abuse?
    assert isinstance(table, macros.MacroTable)


def test_contains(table):
    assert 'foo' in table
    assert 'bar' in table
    assert 'baz' not in table


def test_len(table):
    assert len(table) == 2


def test_get(foo_op, bar_op, table):
    assert table['foo'] is foo_op
    assert table['bar'] is bar_op


def test_dict_like(foo_op, bar_op, table):
    assert dict(table) == {'foo': foo_op, 'bar': bar_op}


def test_keys(table):
    assert set(table) == {'foo', 'bar'}


def test_set(table):
    baz_op = _simple_op_factory('')
    table.set('baz', baz_op)
    assert 'baz' in table
    assert table['baz'] is baz_op


def test_set_existing(table):
    baz_op = _simple_op_factory('')
    table.set('bar', baz_op)
    assert table['bar'] is baz_op


def test_register(table):
    baz_op = _simple_op_factory('')
    table.register('baz')(baz_op)
    assert 'baz' in table
    assert table['baz'] is baz_op


def test_call_func(table):
    assert table('foo', {}) == 'foo_result'


def _op_with_repr_args(a=None, b=None, c=None, context=None):
    """ simple mock op to test if args are set as expected """
    return repr((a, b, c))


def test_call_func_args(table):
    table.set('args', _op_with_repr_args)
    assert table('args', {'a': 1, 'b': 'foo'}) == repr((1, 'foo', None))


def _op_with_repr_context(context=None):
    """ simple mock op to test if context is set as expected """
    return repr(context)


def test_call_func_context(table):
    table.set('ctx', _op_with_repr_context)
    ctx = {'a': 1, 'b': 'foo'}
    assert table('ctx', {}, context=ctx) == repr(ctx)
