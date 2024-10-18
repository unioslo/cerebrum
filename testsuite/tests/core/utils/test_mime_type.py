# -*- coding: utf-8 -*-
""" Tests for :mod:`Cerebrum.utils.mime_type.` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest
import six

from Cerebrum.utils import mime_type


TEST_CASES = [
    (
        "text/plain",
        ("text", "plain", {}),
    ),
    (
        "application/json",
        ("application", "json", {}),
    ),
    (
        "application/x-foo; foo=38;bar=\"test\"",
        ("application", "x-foo", {'foo': "38", 'bar': "test"}),
    ),
    (
        # escape/tspecial parameter values (';', '\\', '\"')
        "text/plain; foo=\"foo;baz\"; bar=\"\\\\test\\\"\"",
        ("text", "plain", {'foo': "foo;baz", 'bar': "\\test\""}),
    ),
    (
        # plaintext with charset parameter
        "text/plain; charset=utf-8",
        ("text", "plain", {'charset': "utf-8"}),
    ),
    (
        # plaintext with quoted charset parameter
        "text/plain; charset=\"utf-8\"",
        ("text", "plain", {'charset': "utf-8"}),
    ),
    # Our current parser implementation doesn't support comments!
    # (
    #     # plaintext with charset and comment
    #     "text/plain; charset=utf-8 (Plain Text)",
    #     ("text", "plain", {'charset': "utf-8"}),
    # ),
    # (
    #     # plaintext with quoted charset and comment
    #     "text/plain; charset=\"utf-8\" (Plain Text)",
    #     ("text", "plain", {'charset': "utf-8"}),
    # ),
]


@pytest.mark.parametrize(
    "value, expected",
    [pytest.param(*t, id=t[0]) for t in TEST_CASES],
)
def test_parse_mime_type(value, expected):
    assert mime_type.parse_mime_type(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "text",
        "/plain",
    ],
)
def test_parse_mime_type_invalid(value):
    with pytest.raises(ValueError):
        print(mime_type.parse_mime_type(value))


@pytest.mark.parametrize(
    "value, expected",
    [
        pytest.param("foo", "foo", id="no-quote"),
        pytest.param("foo bar", "\"foo bar\"", id="space"),
        pytest.param("foo[]", "\"foo[]\"", id="tspecial"),
        pytest.param("foo\"bar", "\"foo\\\"bar\"", id="quote-mark"),
        pytest.param("foo\\bar", "\"foo\\\\bar\"", id="backspace"),
    ],
)
def test_quote_string(value, expected):
    assert mime_type.quote_string(value) == expected


@pytest.mark.parametrize(
    "media_type, media_subtype, parameters, expected",
    [
        pytest.param(
            "text", "plain", {},
            "text/plain",
            id="simple",
        ),
        pytest.param(
            "application", "vnd.api+json", {},
            "application/vnd.api+json",
            id="type/subtype+subtype",
        ),
        pytest.param(
            "application", "X-Foo", {'Foo': "38", 'Bar': "A/B"},
            "application/x-foo; bar=\"A/B\"; foo=38",
            id="normalize",
        ),
    ],
)
def test_mime_time_str(media_type, media_subtype, parameters, expected):
    obj = mime_type.MimeType(media_type, media_subtype, parameters)
    assert six.text_type(obj) == expected


@pytest.mark.parametrize(
    "strval, media_type, media_subtype, parameters",
    [
        pytest.param(
            "text/plain",
            "text", "plain", {},
            id="simple",
        ),
        pytest.param(
            "application/vnd.api+json",
            "application", "vnd.api+json", {},
            id="type/subtype+subtype",
        ),
        pytest.param(
            "Application/X-Foo; Bar=\"A/B\"; Foo=38;",
            "application", "x-foo", {'foo': "38", 'bar': "A/B"},
            id="normalize",
        ),
    ],
)
def test_mime_type_from_string(strval, media_type, media_subtype, parameters):
    obj = mime_type.MimeType.from_string(strval)
    assert obj.media_type == media_type
    assert obj.media_subtype == media_subtype
    assert obj.parameters == parameters


def test_mime_type_repr():
    obj = mime_type.MimeType("text", "plain", {'charset': "utf-8"})
    text = repr(obj)
    assert text == "<MimeType text/plain; charset=utf-8>"
