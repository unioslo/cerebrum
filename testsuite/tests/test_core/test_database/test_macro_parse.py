# -*- coding: utf-8 -*-
"""
tests for Cerebrum.database.macros parsing functionality.
"""
import pytest

from Cerebrum.database import macros


def test_parse_normal_args():
    args = macros.parse_macro_args('foo=value bar=anothervalue')
    assert args == {'foo': 'value', 'bar': 'anothervalue'}


def test_parse_duplicate_args():
    # TODO: should this be an error in stead?
    args = macros.parse_macro_args('foo=value foo=anothervalue')
    assert args == {'foo': 'anothervalue'}


def test_parse_empty_args():
    args = macros.parse_macro_args('')
    assert args == {}


def test_parse_op_only():
    op, args = macros.parse_macro('[:op]')
    assert op == 'op'
    assert args == {}


def test_parse_op_with_arg():
    op, args = macros.parse_macro('[:op foo=asd]')
    assert op == 'op'
    assert args == {'foo': 'asd'}


def test_parse_op_with_args():
    op, args = macros.parse_macro('[:op foo=asd bar=asdz]')
    assert op == 'op'
    assert args == {'foo': 'asd', 'bar': 'asdz'}


def test_parse_excessive_whitespace():
    op, args = macros.parse_macro('[:op   foo=asd   bar=asdz]')
    assert op == 'op'
    assert args == {'foo': 'asd', 'bar': 'asdz'}


invalid_ops = (
    ('[: op foo=asd]', 'leading whitespace'),
    ('[:op foo=asd ]', 'post whitespace'),
    (':op foo=asd', 'missing brackets'),
    ('[op foo=asd]', 'missing colon'),
)


@pytest.mark.parametrize(
    'raw',
    tuple(t[0] for t in invalid_ops),
    ids=tuple(t[1] for t in invalid_ops))
def test_parse_invalid(raw):
    with pytest.raises(ValueError, match='invalid macro string'):
        macros.parse_macro(raw)
