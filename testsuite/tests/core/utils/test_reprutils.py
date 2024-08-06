# -*- coding: utf-8 -*-
"""
Tests for :mod:`Cerebrum.utils.reprutils`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import re

import pytest

import Cerebrum.utils.reprutils

#
# Basic reprutils classes.
#


class FactoryMixin(object):

    @classmethod
    def new(cls, **attrs):
        return type(cls.__name__, (cls,), attrs)


class Fields(FactoryMixin, Cerebrum.utils.reprutils.ReprFieldMixin):

    repr_id = False
    repr_module = False
    repr_fields = ('foo', 'bar', 'missing')

    def __init__(self, foo, bar):
        self.foo = foo
        self.bar = bar


class Eval(FactoryMixin, Cerebrum.utils.reprutils.ReprEvalMixin):

    repr_id = False
    repr_module = False
    repr_args = ('foo', 'bar')
    repr_kwargs = ('baz', 'missing')

    def __init__(self, foo, bar, baz=None):
        self.foo = foo
        self.bar = bar
        self.baz = baz


class EvalArgs(FactoryMixin, Cerebrum.utils.reprutils.ReprEvalMixin):

    repr_id = False
    repr_module = False
    repr_args_attr = '_args'
    repr_kwargs_attr = '_kwargs'

    def __init__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs


#
# Test core features
#


def test_field():
    obj = Fields(str('text'), None)
    assert repr(obj) == "<Fields foo='text' bar=None>"


def test_field_module():
    cls = Fields.new(repr_module=True)
    obj = cls(str('text'), None)
    assert repr(obj).startswith("<{}.Fields".format(__name__))


def test_field_id():
    cls = Fields.new(repr_id=True)
    obj = cls(str('text'), None)
    assert re.match(r"<Fields .* at 0x[0-90a-fA-F]+>$", repr(obj))


def test_eval():
    obj = Eval(str('text'), None, 3)
    assert repr(obj) == "Eval('text', None, baz=3)"


def test_eval_module():
    cls = Eval.new(repr_module=True)
    obj = cls(str('text'), None, 3)
    assert repr(obj) == "{}.Eval('text', None, baz=3)".format(__name__)


def test_eval_arglists():
    obj = EvalArgs(str('text'), None, foo=3)
    assert repr(obj) == "EvalArgs('text', None, foo=3)"


def test_eval_arglists_module():
    cls = EvalArgs.new(repr_module=True)
    obj = cls(str('text'), None, foo=3)
    assert repr(obj) == "{}.EvalArgs('text', None, foo=3)".format(__name__)


def test_eval_arglists_kwargs():
    # Test using more than one kwarg - we no longer know the order
    obj = EvalArgs(foo=None, bar=3)
    value = repr(obj)
    assert "foo=None" in value
    assert "bar=3" in value


#
# Test various field values
#


class SimpleField(Cerebrum.utils.reprutils.ReprFieldMixin):

    repr_id = False
    repr_module = False
    repr_fields = ('value',)

    def __init__(self, value):
        self.value = value


TEST_VALUES = [
    None,
    True,  # bool
    "blåbær".encode("utf-8"),  # bytes
    dict(),
    3.14,  # float
    -31,  # int
    list(),
    object(),
    set(),
    "blåbær",  # str
    tuple(),
]


@pytest.mark.parametrize("value", TEST_VALUES,
                         ids=lambda v: type(v).__name__)
def test_field_value(value):
    f = SimpleField(value)
    assert repr(f) == "<SimpleField value={}>".format(repr(value))


@pytest.mark.parametrize("value", TEST_VALUES,
                         ids=lambda v: type(v).__name__)
def test_eval_value(value):
    f = EvalArgs(value)
    assert repr(f) == "EvalArgs({})".format(repr(value))
