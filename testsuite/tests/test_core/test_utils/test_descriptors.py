#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Unit tests for descriptors. """
from __future__ import print_function, unicode_literals

import pytest

from Cerebrum.utils.descriptors import lazy_property


@pytest.fixture
def foo_class():
    class Foo(object):
        @lazy_property
        def example(self):
            """Bar"""
            return 123
    return Foo


def test_lazy_property(foo_class):
    foo = foo_class()
    assert isinstance(foo_class.example, lazy_property)
    assert foo_class.example.__doc__ == 'Bar'
    assert foo.example == 123
    foo.example = 321
    assert foo.example == 321
    del foo.example
    assert foo.example == 123
