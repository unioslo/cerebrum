# encoding: utf-8
"""
Unit tests for :mod:`Cerebrum.utils.http`
"""

from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

from Cerebrum.utils import http as http_utils


#
# safe_path
#


SAFE_PATH_TESTS = [
    ("foo", "foo"),
    ("foo/bar", "foo%2Fbar"),
    (-3, "-3"),
    ("text-fjøl", "text-fj%C3%B8l"),
    ("utf8-fjøl".encode("utf-8"), "utf8-fj%C3%B8l"),
]


@pytest.mark.parametrize(
    "value, expected",
    SAFE_PATH_TESTS,
    ids=[v for _, v in SAFE_PATH_TESTS],
)
def test_safe_path(value, expected):
    assert http_utils.safe_path(value) == expected


#
# merge_headers
#


def test_merge_headers_empty():
    assert http_utils.merge_headers({}, None, {}) == {}


def test_merge_headers_full_overlap():
    a = {"foo": "1", "bar": "2"}
    b = {"foo": "3", "bar": "4"}
    assert http_utils.merge_headers(a, b) == b


def test_merge_headers_no_overlap():
    a = {"foo": "1"}
    b = {"bar": "2"}
    expected = {"foo": "1", "bar": "2"}
    assert http_utils.merge_headers(a, b) == expected


def test_merge_headers_no_mutate():
    """ Merge headers should not alter the input dicts. """
    a = {"foo": "1"}
    b = {"bar": "2"}
    a_copy = dict(a)
    b_copy = dict(b)
    http_utils.merge_headers(a, b)
    assert a == a_copy
    assert b == b_copy


def test_merge_headers_casing():
    """ Merge headers keep casing from the last seen header name. """
    a = {"X-Foo": "1", "x-Bar": "2"}
    b = {"x-foo": "3", "X-Bar": "4"}
    # should keep last seen value and casing
    expected = {"x-foo": "3", "X-Bar": "4"}
    assert http_utils.merge_headers(a, b) == expected


def test_merge_headers_remove():
    """ Merge headers should omit header values that are set to None. """
    a = {"x-foo": "1", "x-bar": "2"}
    b = {"X-Foo": "3", "X-Bar": None}
    expected = {"X-Foo": "3"}
    assert http_utils.merge_headers(a, b) == expected


#
# urljoin
#


URLJOIN_TESTS = [
    (("http://localhost", "foo"), "http://localhost/foo"),
    (("http://localhost/", "foo"), "http://localhost/foo"),
    (("http://localhost/foo", "bar"), "http://localhost/foo/bar"),
    (("http://localhost/foo//", "bar"), "http://localhost/foo/bar"),
    (("http://localhost", "foo", "bar"), "http://localhost/foo/bar"),
]


@pytest.mark.parametrize(
    "values, expected",
    URLJOIN_TESTS,
    ids=[repr(k) for k, v in URLJOIN_TESTS],
)
def test_urljoin(values, expected):
    assert http_utils.urljoin(*values) == expected
