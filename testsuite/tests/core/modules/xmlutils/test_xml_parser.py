# encoding: utf-8
"""
Unit tests for :mod:`Cerebrum.modules.xmlutils.GeneralXMLParser`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import textwrap

import pytest

from Cerebrum.modules.xmlutils.GeneralXMLParser import GeneralXMLParser
from Cerebrum.testutils import file_utils


@pytest.fixture
def results():
    """ list of results for callback. """
    return []


@pytest.fixture
def callback(results):
    """ a callback that stores all matched elements. """

    def process_element(children, stack):
        tag, attrs = stack[-1]
        result = (tag, attrs, children)
        results.append(result)

    return process_element


EXAMPLE_XML = textwrap.dedent(
    """
    <?xml version="1.0" encoding="utf-8"?>
    <data>
      <foo x="1" y="2">
        <bar x="3" y="4"/>
        <baz x="5" y="6"/>
      </foo>
      <bar x="7" y="8"/>
      <baz x="9" y="10"/>
    </data>
    """
).strip()


def test_parse_full(callback, results, write_xml_file):
    filename = write_xml_file(EXAMPLE_XML)

    # look for <data></data> (i.e., the whole document)
    callbacks = (
        (["data"], callback),
    )
    GeneralXMLParser(callbacks, filename)

    assert len(results) == 1
    tag, attrs, children = results[0]

    assert tag == "data"
    assert attrs == {}

    assert len(children) == 3
    assert children == [
        ['foo', None, {'x': "1", 'y': "2"}, [
            ['bar', None, {'x': "3", 'y': "4"}, []],
            ['baz', None, {'x': "5", 'y': "6"}, []],
        ]],
        ['bar', None, {'x': "7", 'y': "8"}, []],
        ['baz', None, {'x': "9", 'y': "10"}, []],
    ]


def test_dump_tree_full(capsys, callback, results, write_xml_file):
    filename = write_xml_file(EXAMPLE_XML)

    # look for <data></data> (i.e., the whole document)
    callbacks = (
        (["data"], callback),
    )
    GeneralXMLParser(callbacks, filename)

    GeneralXMLParser.dump_tree(results)
    stdout, _ = capsys.readouterr()
    lines = stdout.splitlines()
    assert lines[0] == "data {}"
    # No guarantee of attribute ordering, let's just check line start
    assert lines[1].startswith("  foo {")
    assert lines[2].startswith("    bar {")
    assert len(lines) == 6


def test_parse_xmlpath(callback, results, write_xml_file):
    filename = write_xml_file(EXAMPLE_XML)

    # look for <data></data> (i.e., the whole document)
    callbacks = (
        (["data", "foo", "bar"], callback),
    )
    GeneralXMLParser(callbacks, filename)

    assert len(results) == 1
    tag, attrs, children = results[0]

    assert tag == "bar"
    assert attrs == {'x': "3", 'y': "4"}
    assert children == []


def test_parse_xmlpath_multiple(callback, results, write_xml_file):
    filename = write_xml_file(EXAMPLE_XML)

    # look for <data></data> (i.e., the whole document)
    callbacks = (
        (["data", "foo", "bar"], callback),
        (["data", "baz"], callback),
    )
    GeneralXMLParser(callbacks, filename)

    assert len(results) == 2

    tag, attrs, children = results[0]
    assert tag == "bar"
    assert attrs == {'x': "3", 'y': "4"}
    assert children == []

    tag, attrs, children = results[1]
    assert tag == "baz"
    assert attrs == {'x': "9", 'y': "10"}
    assert children == []


#
# Verify that External General Entities are disabled
#


@pytest.fixture
def secret_file(write_dir):
    """ a writer that creates a temporary .xml file with the given content. """
    with file_utils.tempfile_ctx(write_dir, suffix=".txt") as filename:
        file_utils.write_text(filename, "secret text")
        yield filename


def test_parse_no_xxe(secret_file, callback, results, write_xml_file):
    malicious_xml = textwrap.dedent(
        """
        <?xml version="1.0" encoding="utf-8"?>
        <!DOCTYPE foo [
            <!ELEMENT foo ANY>
                <!ENTITY xxe SYSTEM "file://{}">]>
        <data>
          <foo>&xxe;</foo>
          <foo>plaintext</foo>
        </data>
        """
    ).lstrip().format(secret_file)
    filename = write_xml_file(malicious_xml)

    callbacks = (
        (["data"], callback),
    )
    GeneralXMLParser(callbacks, filename)

    print(results)
    assert len(results) == 1
    tag, attrs, children = results[0]

    assert tag == "data"
    assert attrs == {}
    assert children == [
        # if we get "secret text" in stead of None, we're vulnerable to xee
        ["foo", None, {}, []],
        ["foo", "plaintext", {}, []],
    ]
