# -*- coding: utf-8 -*-
""" Tests for `Cerebrum.modules.bofhd.protocol` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import textwrap

import pytest
import six

from Cerebrum.modules.bofhd import errors as bofhd_errors
from Cerebrum.modules.bofhd import protocol as bofhd_proto


#
# sanitize()
#

CHAR_TAB = 0x09
CHAR_CR = 0x0A
CHAR_LF = 0x0D
CONTROL_CHARS = set(six.unichr(u) for u in six.moves.range(0x00, 0x1F))
CONTROL_CHARS_KEEP = set(six.unichr(u) for u in (CHAR_TAB, CHAR_CR, CHAR_LF))
CONTROL_CHARS_SKIP = CONTROL_CHARS - CONTROL_CHARS_KEEP


@pytest.mark.parametrize("s", ("foo".encode("ascii"), "foo"))
def test_sanitize_string_coercion(s):
    assert isinstance(bofhd_proto.sanitize(s), six.text_type)


@pytest.mark.parametrize("char", list(sorted(CONTROL_CHARS_SKIP)))
def test_sanitize_strip_control_characters(char):
    assert bofhd_proto.sanitize(char) == ""


@pytest.mark.parametrize("char", list(sorted(CONTROL_CHARS_KEEP)))
def test_sanitize_preserve_line_feeds(char):
    assert bofhd_proto.sanitize(char) == char


@pytest.mark.parametrize("actual,expected", (
    ("foo\x08", "foo"),
    ("foo\x08bar",  "foobar"),
    ("\x08bar", "bar"),
))
def test_sanitize_mixed_control_characters(actual, expected):
    assert bofhd_proto.sanitize(actual) == expected


def test_sanitize_lists():
    lst = ["foo", ["bar"]]
    assert bofhd_proto.sanitize(lst) == lst


def test_sanitize_tuples():
    assert bofhd_proto.sanitize(("foo", ("bar",))) == ["foo", ["bar"]]


def test_sanitize_dict():
    d = {"foo": {"bar": "baz"}}
    assert bofhd_proto.sanitize(d) == d


@pytest.mark.parametrize("t", (None, True, object()))
def test_sanitize_other_types(t):
    assert type(bofhd_proto.sanitize(t)) == type(t)
    assert bofhd_proto.sanitize(t) == t


#
# loads()/dumps()
#


def test_dumps_response():
    resp = {"foo": ["bar", 3]}

    assert bofhd_proto.dumps(resp) == textwrap.dedent(
        """
        <?xml version='1.0'?>
        <methodResponse>
        <params>
        <param>
        <value><struct>
        <member>
        <name>foo</name>
        <value><array><data>
        <value><string>bar</string></value>
        <value><int>3</int></value>
        </data></array></value>
        </member>
        </struct></value>
        </param>
        </params>
        </methodResponse>
        """
    ).lstrip()


XMLRPC_FAULT_FMT = textwrap.dedent(
    """
    <?xml version='1.0'?>
    <methodResponse>
    <fault>
    <value><struct>
    <member>
    <name>faultCode</name>
    <value><int>{code:d}</int></value>
    </member>
    <member>
    <name>faultString</name>
    <value><string>{value}</string></value>
    </member>
    </struct></value>
    </fault>
    </methodResponse>
    """
).lstrip()


def test_dumps_generic_exception():
    msg = "invalid value: 'foo'"
    exc = ValueError(msg)
    assert bofhd_proto.dumps(exc) == XMLRPC_FAULT_FMT.format(
        code=2,
        value=("ValueError:" + msg),
    )


def test_dumps_bofhd_error():
    msg = "invalid value: 'foo'"
    exc = bofhd_errors.CerebrumError(msg)
    assert bofhd_proto.dumps(exc) == XMLRPC_FAULT_FMT.format(
        code=1,
        value=("Cerebrum.modules.bofhd.errors.CerebrumError:" + msg),
    )
