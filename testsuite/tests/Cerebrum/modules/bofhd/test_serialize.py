# -*- coding: utf-8 -*-

import pytest
import six

from Cerebrum.modules.bofhd.handler import BofhdRequestHandler


serialize = BofhdRequestHandler._serialize


@pytest.mark.parametrize("s", ["foo", six.text_type("foo")])
def test_string_coercion(s):
    assert isinstance(serialize(s), six.text_type)


@pytest.mark.parametrize("rune", six.moves.range(0x00, 0x1F))
def test_strip_control_characters(rune):
    # skip TAB, CR, and LF
    if rune not in (0x09, 0x0A, 0x0D):
        assert serialize(unichr(rune)) == six.text_type("")


@pytest.mark.parametrize("actual,expected", [
    ("foo\x08", "foo"),
    ("foo\x08bar",  "foobar"),
    ("\x08bar", "bar"),
])
def test_mixed_control_characters(actual, expected):
    assert serialize(actual) == expected


@pytest.mark.parametrize("rune", ["\t", "\r", "\n"])
def test_preserve_line_feeds(rune):
    assert serialize(rune) == rune


@pytest.mark.parametrize("seq", [["foo", ["bar"]], ("foo", ("bar",))])
def test_collection(seq):
    assert serialize(seq) == [six.text_type("foo"), [six.text_type("bar")]]


def test_dict():
    assert serialize({u"foo": {u"bar": "baz"}}) == {u"foo": {u"bar": u"baz"}}


@pytest.mark.parametrize("t", [None, True, object()])
def test_other_types(t):
    assert type(serialize(t)) == type(t)
    assert serialize(t) == t
