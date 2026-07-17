# encoding: utf-8
"""
Unit tests for :mod:`Cerebrum.utils.mappings`.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest
import six

from Cerebrum.utils import mappings


#
# SimpleMap tests
#

SIMPLEMAP_DATA = {"foo": "text", "bar": 3}


def test_simplemap_init_empty():
    d = mappings.SimpleMap()
    assert isinstance(d, mappings.Mapping)
    assert dict(d) == {}


def test_simplemap_transform_key():
    m = mappings.SimpleMap()
    assert m.transform_key("Example") == "Example"


def test_simplemap_transform_value():
    m = mappings.SimpleMap()
    assert m.transform_value("Example") == "Example"


def test_simplemap_init_dict():
    init = dict(SIMPLEMAP_DATA)
    d = mappings.SimpleMap(init)
    assert dict(d) == init


def test_simplemap_init_tuples():
    init = dict(SIMPLEMAP_DATA)
    d = mappings.SimpleMap(list(init.items()))
    assert dict(d) == init


def test_simplemap_init_kwargs():
    init = dict(SIMPLEMAP_DATA)
    d = mappings.SimpleMap(**init)
    assert dict(d) == init


@pytest.fixture
def simple_map():
    return mappings.SimpleMap(**SIMPLEMAP_DATA)


def test_simplemap_len(simple_map):
    assert len(simple_map) == len(SIMPLEMAP_DATA)


def test_simplemap_iter(simple_map):
    iterator = iter(simple_map)
    remaining = set(SIMPLEMAP_DATA)
    for _ in range(len(SIMPLEMAP_DATA)):
        remaining.remove(next(iterator))
    assert not remaining


def test_simplemap_getitem_hit(simple_map):
    assert simple_map["foo"] == "text"
    assert simple_map["bar"] == 3


def test_simplemap_getitem_miss(simple_map):
    with pytest.raises(KeyError):
        simple_map["missing"]


def test_simplemap_contains_hit(simple_map):
    assert "foo" in simple_map
    assert "bar" in simple_map


def test_simplemap_contains_miss(simple_map):
    assert "missing" not in simple_map


def test_simplemap_set(simple_map):
    assert "new-key" not in simple_map
    simple_map.set("new-key", "new-value")
    simple_map["new-key"] == "new-value"


def test_simplemap_repr(simple_map):
    assert repr(simple_map)


def test_simplemap_keys(simple_map):
    assert set(simple_map.keys()) == set(SIMPLEMAP_DATA.keys())


def test_simplemap_values(simple_map):
    assert set(simple_map.values()) == set(SIMPLEMAP_DATA.values())


def test_simplemap_items(simple_map):
    assert set(simple_map.items()) == set(SIMPLEMAP_DATA.items())


# TODO: Add repr recursion protection
# TODO: Test repr recursion


@pytest.mark.filterwarnings("ignore:view:DeprecationWarning")
def test_simplemap_viewkeys(simple_map):
    view = simple_map.viewkeys()
    assert "new-key" not in view
    simple_map.set("new-key", "new-value")
    assert "new-key" in view


@pytest.mark.filterwarnings("ignore:view:DeprecationWarning")
def test_simplemap_viewvalues(simple_map):
    view = simple_map.viewvalues()
    assert "new-value" not in view
    simple_map.set("new-key", "new-value")
    assert "new-value" in view


@pytest.mark.filterwarnings("ignore:view:DeprecationWarning")
def test_simplemap_viewitems(simple_map):
    view = simple_map.viewitems()
    assert ("new-key", "new-value") not in view
    simple_map.set("new-key", "new-value")
    assert ("new-key", "new-value") in view


#
# Test SimpleMap transforms
#

class TestMap(mappings.SimpleMap):

    def transform_key(self, key):
        return six.text_type(key).lower()

    def transform_value(self, value):
        return six.text_type(value).lower()


@pytest.fixture
def transform_map():
    m = TestMap()
    m.set("FOO", -3)
    return m


def test_transform_set(transform_map):
    assert list(transform_map.values()) == ["-3"]


def test_transform_len(transform_map):
    assert len(transform_map) == 1


def test_transform_contains(transform_map):
    assert "foo" in transform_map
    assert "FOO" in transform_map
    assert "Foo" in transform_map


def test_transform_getitem(transform_map):
    assert transform_map["foo"] == "-3"


def test_transform_iter(transform_map):
    assert list(transform_map) == ["foo"]


#
# DecoratorMap tests
#
def test_decorator_map_get_wrapper():
    m = mappings.DecoratorMap()
    wrapper = m.register("foo")
    assert "foo" not in m  # yet
    assert callable(wrapper)


def test_decorator_map_register_func():
    m = mappings.DecoratorMap()
    m.register("lower")(str.lower)
    assert "lower" in m
    assert m["lower"] is str.lower


def test_decorator_map_decorate():
    m = mappings.DecoratorMap()

    @m.register("my-func")
    def my_func():
        pass

    assert "my-func" in m
    assert m["my-func"] is my_func
