#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Tests for the rest.context utils. """

import pytest


@pytest.fixture
def ContextValue():
    import Cerebrum.rest.api.context as _ctx_module
    return _ctx_module.ContextValue


@pytest.fixture
def Container(ContextValue):
    class Container_obj(object):
        default = 'default'
        foo = ContextValue('foo')
        foo_dup = ContextValue('foo', default)
        bar = ContextValue('bar', default)

        def __init__(self, **kwargs):
            """ init with values. """
            for k in kwargs:
                if hasattr(self, k):
                    setattr(self, k, kwargs[k])
    return Container_obj


def test_get_descriptor(app_ctx, Container, ContextValue):
    assert isinstance(Container.foo, ContextValue)


def test_default_value(app_ctx, Container):
    c = Container()
    assert c.bar == Container.bar.default == Container.default


def test_set_value(app_ctx, Container):
    c = Container()
    assert c.bar != 'baz'
    # after setting, the value should be retained
    c.bar = 'baz'
    assert c.bar == 'baz'


def test_init(app_ctx, Container):
    # make sure that out test object works as expected
    c = Container(foo_dup='foo', bar='bar')
    assert c.foo_dup == 'foo'
    assert c.bar == 'bar'


def test_del_value(app_ctx, Container):
    c = Container(bar='baz')
    assert c.bar == 'baz' != Container.bar.default
    # deleting should return value to default
    del c.bar
    assert c.bar == Container.bar.default


def test_get_default_duplicate_values(app_ctx, Container):
    assert Container.foo.default != Container.foo_dup.default
    c = Container()
    # unset duplicate values should be able to have different defaults
    assert c.foo != c.foo_dup


def test_set_duplicate_value(app_ctx, Container):
    c = Container()
    assert c.foo == Container.foo.default != 'baz'
    # setting one should change the other
    c.foo = 'baz'
    assert c.foo == c.foo_dup == 'baz'


def test_del_duplicate_value(app_ctx, Container):
    c = Container(foo='foo')
    assert c.foo == c.foo_dup == 'foo'
    # deleting one should return both to their individual defaults
    del c.foo_dup
    assert c.foo == Container.foo.default
    assert c.foo_dup == Container.foo_dup.default
