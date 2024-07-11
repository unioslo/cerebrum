# -*- coding: utf-8 -*-
""" Tests for mod:`Cerebrum.modules.descriptors`. """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

from Cerebrum.utils import descriptors


DEFAULT_VALUE = 123


@pytest.fixture
def foo_class():
    class Foo(object):
        @descriptors.lazy_property
        def example(self):
            """Bar"""
            return DEFAULT_VALUE
    return Foo


def test_lazy_property_get_class(foo_class):
    """ getting a property from a class should return the property itself. """
    assert isinstance(foo_class.example, descriptors.lazy_property)


def test_lazy_property_docstring(foo_class):
    """ the property should get its docstring from its wrapped method. """
    assert foo_class.example.__doc__ == "Bar"


def test_lazy_property_default(foo_class):
    """ getting an unset value should work (and cache its value). """
    foo = foo_class()
    assert foo.example == DEFAULT_VALUE


def test_lazy_property_set(foo_class):
    """ setting a custom value should work (override the wrapped default). """
    foo = foo_class()
    foo.example = 321
    assert foo.example == 321


def test_lazy_property_del(foo_class):
    """ deleting a property should reset it to its default. """
    foo = foo_class()
    foo.example = 321
    del foo.example
    assert foo.example == DEFAULT_VALUE


def test_lazy_property_del_default(foo_class):
    """ deleting an unset property should work (do nothing). """
    foo = foo_class()
    del foo.example
    assert foo.example == DEFAULT_VALUE
