# -*- coding: utf-8 -*-
"""
Unit tests for mod:`Cerebrum.utils.sorting`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest
import six

from Cerebrum.utils import sorting


#
# make_priority_lookup tests
#


def test_make_priority_lookup_init():
    lut = sorting.make_priority_lookup(["foo", "bar", "baz"])
    assert callable(lut)


def test_make_priority_lookup_mixed_type():
    lut = sorting.make_priority_lookup(["foo", True, 3.14])
    assert callable(lut)


def test_make_priority_lookup_duplicate():
    with pytest.raises(ValueError) as exc_info:
        sorting.make_priority_lookup(["foo", "bar", "foo"])

    msg = six.text_type(exc_info.value)
    assert msg.startswith("Duplicate value")
    assert repr("foo") in msg


def test_priority_lookup_value():
    lut = sorting.make_priority_lookup(["foo", "bar", "baz"])
    assert lut("foo") == 0
    assert lut("bar") == 1
    assert lut("baz") == 2


def test_priority_lookup_default():
    lut = sorting.make_priority_lookup(["foo", "bar", "baz"])
    assert lut("unknown") == 3


def test_inverse_priority_lookup_value():
    lut = sorting.make_priority_lookup(["foo", "bar", "baz"],
                                       invert=True)
    lut("foo") == 3
    lut("bar") == 2
    lut("baz") == 1


def test_inverse_priority_lookup_default():
    lut = sorting.make_priority_lookup(["foo", "bar", "baz"],
                                       invert=True)
    assert lut("unknown") == 0


def test_priority_lookup_sort_key():
    lut = sorting.make_priority_lookup(["foo", "bar", "baz"])
    values = ["unknown", "bar", "baz", "foo"]
    result = sorted(values, key=lut)
    assert result == ["foo", "bar", "baz", "unknown"]
