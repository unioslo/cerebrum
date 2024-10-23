# -*- coding: utf-8 -*-
"""
Tests for :mod:`Cerebrum.database.paramstyles`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import re

import pytest
import six

from Cerebrum.database import paramstyles


all_paramstyles = (
    ('qmark', paramstyles.Qmark),
    ('format', paramstyles.Format),
    ('numeric', paramstyles.Numeric),
    ('named', paramstyles.Named),
    ('pyformat', paramstyles.Pyformat),
)
all_names = tuple(t[0] for t in all_paramstyles)
all_classes = tuple(t[1] for t in all_paramstyles)


@pytest.mark.parametrize("style, expected", all_paramstyles, ids=all_names)
def test_get_converter(style, expected):
    cls = paramstyles.get_converter(style)
    assert cls is expected


def test_get_converter_unknown():
    with pytest.raises(NotImplementedError) as exc_info:
        paramstyles.get_converter("unknown-style")

    error_msg = six.text_type(exc_info.value)
    assert "No converter for param_style" in error_msg


@pytest.mark.parametrize("cls", all_classes, ids=all_names)
def test_register(cls):
    """ verify that register() stores param names """
    c = cls()
    assert 'foo' not in c
    assert 'bar' not in c
    c.register('foo')
    c.register('bar')
    assert 'foo' in c
    assert 'bar' in c


@pytest.mark.parametrize("cls", all_classes, ids=all_names)
def test_repr(cls):
    c = cls()
    c.register('foo')
    c.register('bar')
    match = re.match(
        r"<(?P<name>[A-Za-z]+) names=\[u?'foo', u?'bar'\] at ",
        repr(c),
    )
    assert match
    assert match.group("name") == cls.__name__


def test_qmark_value():
    c = paramstyles.Qmark()
    assert c.register('foo') == '?'


def test_qmark_convert():
    c = paramstyles.Qmark()
    c.register('foo')
    c.register('bar')
    assert c({'foo': 1, 'bar': 2}) == (1, 2)


def test_qmark_convert_expand():
    c = paramstyles.Qmark()
    c.register('foo')
    c.register('foo')
    c.register('bar')
    assert c({'foo': 1, 'bar': 2}) == (1, 1, 2)


def test_format_value():
    c = paramstyles.Format()
    assert c.register('foo') == '%s'


def test_format_convert():
    c = paramstyles.Format()
    c.register('foo')
    c.register('bar')
    assert c({'foo': 1, 'bar': 2}) == (1, 2)


def test_format_convert_expand():
    c = paramstyles.Format()
    c.register('foo')
    c.register('foo')
    c.register('bar')
    assert c({'foo': 1, 'bar': 2}) == (1, 1, 2)


def test_numeric_value():
    c = paramstyles.Numeric()
    assert c.register('foo') == ':1'


def test_numeric_value_multi():
    c = paramstyles.Numeric()
    assert c.register('foo') == ':1'
    # new name, should yield new number
    assert c.register('bar') == ':2'
    # seen name, should yield old number
    assert c.register('foo') == ':1'


def test_numeric_convert():
    c = paramstyles.Numeric()
    c.register('foo')
    c.register('bar')
    assert c({'foo': 1, 'bar': 2}) == (1, 2)


def test_numeric_convert_noexpand():
    c = paramstyles.Numeric()
    c.register('foo')
    c.register('foo')
    c.register('bar')
    assert c({'foo': 1, 'bar': 2}) == (1, 2)


def test_named_value():
    c = paramstyles.Named()
    assert c.register('foo') == ':foo'


def test_named_convert():
    c = paramstyles.Named()
    c.register('foo')
    c.register('bar')
    assert c({'foo': 1, 'bar': 2}) == {'foo': 1, 'bar': 2}


def test_named_convert_noexpand():
    c = paramstyles.Named()
    c.register('foo')
    c.register('foo')
    c.register('bar')
    assert c({'foo': 1, 'bar': 2}) == {'foo': 1, 'bar': 2}


def test_pyformat_value():
    c = paramstyles.Pyformat()
    assert c.register('foo') == '%(foo)s'


def test_pyformat_convert():
    c = paramstyles.Pyformat()
    c.register('foo')
    c.register('bar')
    assert c({'foo': 1, 'bar': 2}) == {'foo': 1, 'bar': 2}


def test_pyformat_convert_noexpand():
    c = paramstyles.Pyformat()
    c.register('foo')
    c.register('foo')
    c.register('bar')
    assert c({'foo': 1, 'bar': 2}) == {'foo': 1, 'bar': 2}


@pytest.mark.parametrize("cls", all_classes, ids=all_names)
def test_convert_missing(cls):
    c = cls()
    c.register('foo')
    c.register('bar')
    with pytest.raises(ValueError):
        c({'foo': 1})  # bar is missing


# TODO: We get different behaviour here from our converters:
#
# - ordered/numbered only returns the registered names
# - named also includes the unregistered parameters
#
# We should decide on a consistent behaviour here:
#
# 1. All our converters should at least filter out/omit any unregistered
#    parameters, but we need to verify that this doesn't break anything.
#
# 2. Providing an unregistered parameter should probably also be an error, as
#    this would force us to write cleaner code, but this will *definitely*
#    break a lot of existing queries.
#
@pytest.mark.parametrize("cls", all_classes, ids=all_names)
def test_convert_invalid(cls):
    if cls in (paramstyles.Named, paramstyles.Pyformat):
        pytest.skip("doesn't behave as expected")
    c = cls()
    c.register('foo')
    result = c({'foo': 1, 'bar': 2})  # bar hasn't been registered
    assert len(result) == 1
