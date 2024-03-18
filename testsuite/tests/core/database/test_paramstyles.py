# -*- coding: utf-8 -*-
"""
tests for Cerebrum.database.paramstyles
"""
import pytest

from Cerebrum.database import paramstyles


allparamstyles = (
    ('qmark', paramstyles.Qmark),
    ('format', paramstyles.Format),
    ('numeric', paramstyles.Numeric),
    ('named', paramstyles.Named),
    ('pyformat', paramstyles.Pyformat),
)
all_names = tuple(t[0] for t in allparamstyles)
all_classes = tuple(t[1] for t in allparamstyles)


@pytest.mark.parametrize("style,expected", allparamstyles, ids=all_names)
def test_get_converter(style, expected):
    """ verify that param style can be retrieved by name """
    cls = paramstyles.get_converter(style)
    assert cls is expected


@pytest.mark.parametrize("cls", all_classes, ids=all_names)
def test_retain(cls):
    """ verify that register() store param names """
    c = cls()
    assert 'foo' not in c
    assert 'bar' not in c
    c.register('foo')
    c.register('bar')
    assert 'foo' in c
    assert 'bar' in c


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
