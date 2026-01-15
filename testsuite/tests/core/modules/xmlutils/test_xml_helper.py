# coding: utf-8
"""
Unit tests for :mod:`Cerebrum.modules.xmlutils.xml2object`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime

import pytest

from Cerebrum.modules.xmlutils import xml_helper


@pytest.fixture
def helper():
    return xml_helper.XMLHelper()


def test_xml_helper_init(helper):
    assert helper
    hdr = '<?xml version="1.0" encoding="utf-8"?>\n'
    assert helper.xml_hdr == hdr


def test_xml_conv_colnames(helper):
    input_cols = ("FOO", "FOO.BAR", "baz", "b.bat")
    expected = ("foo", "bar", "baz", "bat")

    input_list = list(input_cols)
    output = helper.conv_colnames(input_list)

    # We should probably change this:
    assert output is input_list

    assert tuple(output) == expected


class MxLike(object):
    """ A minimal mock mx-like datetime object.  """

    def __init__(self, dt):
        self._dt = dt

    @property
    def year(self):
        return self._dt.year

    @property
    def month(self):
        return self._dt.month

    @property
    def day(self):
        return self._dt.day

    @property
    def hour(self):
        return self._dt.hour

    @property
    def minute(self):
        return self._dt.minute

    @property
    def second(self):
        return self._dt.second + self._dt.microsecond / 1000000

    def pydate(self):
        return self._dt.date()

    def pydatetime(self):
        return self._dt.replace()

    def pytime(self):
        return self._dt.time()


DATETIME = datetime.datetime(2025, 1, 15, 12, 30)
MX_LIKE = MxLike(DATETIME)


@pytest.mark.parametrize(
    "value, expected",
    [
        pytest.param(1, '"1"', id="int"),
        pytest.param("foo", '"foo"', id="str"),
        pytest.param(MX_LIKE, '"2025-01-15 12:30:00.00"', id="mx-datetime"),
        pytest.param(DATETIME, '"2025-01-15 12:30:00.00"', id="datetime"),
        pytest.param("s & \" < > e", '"s &amp; &quot; &lt; &gt; e"',
                     id="special"),
    ],
)
def test_xml_escape_attrs(helper, value, expected):
    assert helper.escape_xml_attr(value) == expected


def test_xmlify_dbrow(helper):
    cols = ("foo", "bar")
    row = dict(zip(cols, ("foo-value", "bar-value")))
    tag = "example"

    expected = '<example foo="foo-value" bar="bar-value"/>'
    result = helper.xmlify_dbrow(row, cols, tag)
    assert result == expected


def test_xmlify_dbrow_no_close(helper):
    cols = ("foo", "bar")
    row = dict(zip(cols, ("foo-value", "bar-value")))
    tag = "example"

    expected = '<example foo="foo-value" bar="bar-value">'
    result = helper.xmlify_dbrow(row, cols, tag, close_tag=0)
    assert result == expected


def test_xmlify_dbrow_extra(helper):
    cols = ("foo", "bar")
    row = dict(zip(cols, ("foo-value", "bar-value")))
    tag = "example"
    extra = {'x': 1}

    expected = '<example foo="foo-value" bar="bar-value" x="1"/>'
    result = helper.xmlify_dbrow(row, cols, tag, extra_attr=extra)
    assert result == expected


def test_xmlify_dbrow_none(helper):
    cols = ("foo", "bar")
    row = dict(zip(cols, ("foo-value", None)))
    tag = "example"

    expected = '<example foo="foo-value"/>'
    result = helper.xmlify_dbrow(row, cols, tag)
    assert result == expected
