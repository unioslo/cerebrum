# -*- coding: utf-8 -*-
""" Tests for mod:`Cerebrum.utils.aggregate.` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

from Cerebrum.utils import aggregate


class Container(object):
    """ A comparable, unhashable container. """

    def __init__(self, value):
        self._value = value

    def __eq__(self, other):
        if hasattr(other, "get_value"):
            return self._value == other.get_value()
        return NotImplemented

    def __ne__(self, other):
        return not self.__eq__(other)

    # Python 2 backwards compatibility.  PY2 implements __hash__ from __eq__,
    # but we want our class to be unhashable - and thus unusable as a key in
    # our aggregating functions.
    __hash__ = None

    def get_value(self):
        return self._value


def test_container_eq():
    assert Container("foo") == Container("foo")


def test_container_ne():
    assert Container("foo") != Container("bar")


def test_container_get_value():
    assert Container("foo").get_value() == "foo"


def test_container_unhashable():
    with pytest.raises(TypeError):
        hash(Container("foo"))


#
# Test aggregate.unique
#

UNIQUE_INPUT = ["foo", "bar", "foo", "baz", "bar", "foo", "baz", "foo"]
UNIQUE_OUTPUT = ["foo", "bar", "baz"]


def test_unique():
    assert list(aggregate.unique(UNIQUE_INPUT)) == UNIQUE_OUTPUT


def test_unique_key():
    input_objs = [Container(k) for k in UNIQUE_INPUT]
    result = list(aggregate.unique(input_objs, key=Container.get_value))
    assert result == [Container(k) for k in UNIQUE_OUTPUT]


#
# Test aggregate.dict_collect_*
#


def test_dict_collect_sets():
    tuples = [('foo', 1), ('foo', 2), ('bar', 2), ('foo', 1)]
    output = {'foo': set([1, 2]), 'bar': set([2])}
    assert aggregate.dict_collect_sets(tuples) == output


def test_dict_collect_lists():
    tuples = [('foo', 1), ('foo', 2), ('bar', 2), ('foo', 1)]
    output = {'foo': [1, 2, 1], 'bar': [2]}
    assert aggregate.dict_collect_lists(tuples) == output


def test_dict_collect_first():
    tuples = [('foo', 1), ('foo', 2), ('bar', 3), ('foo', 4)]
    output = {'foo': 1, 'bar': 3}
    assert aggregate.dict_collect_first(tuples) == output
