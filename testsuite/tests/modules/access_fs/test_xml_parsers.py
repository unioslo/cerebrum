# -*- coding: utf-8 -*-
""" unit tests for :mod:`Cerebrum.modules.no.access_FS`. """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import textwrap

import pytest
import six

from Cerebrum.modules.no import access_FS


#
# _BaseParser helper fixtures
#


@pytest.fixture
def results():
    """ list of results for callback. """
    return []


@pytest.fixture
def callback(results):
    """ a callback that stores all matched elements. """

    def process_element(name, attrs):
        # make attrs a sorted tuple of (key, value) pairs
        # for later comparison
        pairs = tuple(sorted(attrs.items()))
        results.append((name, pairs))

    return process_element


#
# element_attribute_xml_parser tests
#


class AttrsParser(access_FS.element_attribute_xml_parser):

    elements = {
        'data': False,
        'foo': True,
        'bar': True,
        'baz': False,
    }


def test_element_attribute_xml_parser(callback, results, write_xml_file):
    content = textwrap.dedent(
        """
        <?xml version="1.0" encoding="utf-8"?>
        <data>
        <foo x="1" y="2">
          <bar x="3" y="4"/>
        </foo>
        <bar x="5" y="6"/>
        <baz x="7" y="8"/>
        </data>
        """
    ).strip()
    filename = write_xml_file(content)

    AttrsParser(filename, callback)
    assert len(results) == 3
    assert results == [
        # foo "starts" first, and should be the first element processed
        ("foo", (("x", "1"), ("y", "2"))),
        ("bar", (("x", "3"), ("y", "4"))),
        ("bar", (("x", "5"), ("y", "6"))),
    ]


def test_element_attribute_invalid_element(callback, results, write_xml_file):
    content = textwrap.dedent(
        """
        <?xml version="1.0" encoding="utf-8"?>
        <data>
        <foo id="1"/>
        <bar id="2"/>
        <baz id="3"/>
        <quux id="4"/>
        </data>
        """
    ).strip()
    filename = write_xml_file(content)

    with pytest.raises(ValueError) as exc_info:
        AttrsParser(filename, callback)

    msg = six.text_type(exc_info.value)
    expected = "Unknown XML element: %s" % repr("quux")

    assert msg == expected


#
# non_nested_xml_parser tests
#


class FlatParser(access_FS.non_nested_xml_parser):

    elements = {
        'data': False,
        'foo': True,
        'bar': True,
        'baz': False,
    }


def test_non_nested_xml_parser(callback, results, write_xml_file):
    content = textwrap.dedent(
        """
        <?xml version="1.0" encoding="utf-8"?>
        <data>
        <foo id="1"/>
        <bar id="2"/>
        <baz id="3"/>
        <foo id="4"/>
        </data>
        """
    ).strip()
    filename = write_xml_file(content)

    FlatParser(filename, callback)
    assert len(results) == 3
    assert results == [
        ("foo", (("id", "1"),)),
        ("bar", (("id", "2"),)),
        ("foo", (("id", "4"),)),
    ]


def test_non_nested_xml_parser_nesting(callback, results, write_xml_file):
    content = textwrap.dedent(
        """
        <?xml version="1.0" encoding="utf-8"?>
        <data>
        <foo id="1"/>
        <bar id="2">
          <foo id="3"/>
        </bar>
        </data>
        """
    ).strip()
    filename = write_xml_file(content)

    with pytest.raises(RuntimeError) as exc_info:
        FlatParser(filename, callback)

    msg = six.text_type(exc_info.value)
    expected = "Can't deal with nested elements (<foo> before </bar>)."

    assert msg == expected
