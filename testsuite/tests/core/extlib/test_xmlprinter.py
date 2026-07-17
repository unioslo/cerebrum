# encoding: utf-8
""" Tests for mod:`Cerebrum.extlib.xmlprinter` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import io
import textwrap

import pytest

from Cerebrum.extlib import xmlprinter


#
# A doctest ported from the original module
#


def test_xmlprinter():
    fp = io.BytesIO()
    xp = xmlprinter.xmlprinter(fp)
    xp.startDocument()
    xp.notationDecl("html")
    xp.startElement("html")
    xp.data("\n")

    xp.startElement("head")
    xp.startElement("title")
    xp.data("This is the title")
    # end "<title>" (implicit element name)
    xp.endElement()
    # end "head" (explicit element name)
    xp.endElement("head")
    xp.data("\n")

    xp.startElement("body")
    xp.data("\n")
    xp.startElement("p")
    xp.data("This is some information in a paragraph.")
    xp.endElement("p")
    xp.data("\n")
    xp.emptyElement("hr", {'style': "color: red"})
    xp.data("\n")
    # closes remaining tags:
    xp.endDocument()

    bytestr = fp.getvalue()
    assert bytestr.decode("utf-8") == textwrap.dedent(
        """
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE html>
        <html>
        <head><title>This is the title</title></head>
        <body>
        <p>This is some information in a paragraph.</p>
        <hr style="color: red"/>
        </body></html>
        """
    ).lstrip()


#
# Test some error handling
#


@pytest.fixture
def new_xml():
    fp = io.BytesIO()
    return xmlprinter.xmlprinter(fp)


def test_double_start(new_xml):
    new_xml.startDocument()
    with pytest.raises(xmlprinter.WellFormedError):
        new_xml.startDocument()


def test_double_declaration(new_xml):
    new_xml.startDocument()
    new_xml.notationDecl("html")
    with pytest.raises(xmlprinter.WellFormedError):
        new_xml.notationDecl("html")


def test_double_end(new_xml):
    new_xml.startDocument()
    new_xml.endDocument()
    with pytest.raises(xmlprinter.WellFormedError):
        new_xml.endDocument()


def test_end_wrong_element(new_xml):
    new_xml.startDocument()
    new_xml.notationDecl("html")
    new_xml.startElement("head")
    new_xml.startElement("title")
    with pytest.raises(xmlprinter.WellFormedError):
        new_xml.endElement("head")


def test_add_element_after_end(new_xml):
    new_xml.startDocument()
    new_xml.notationDecl("html")
    new_xml.endDocument()
    with pytest.raises(xmlprinter.WellFormedError):
        new_xml.startElement("head")


def test_end_unfinished(new_xml):
    new_xml.startDocument()
    new_xml.notationDecl("html")
    new_xml.startElement("html")
    new_xml.startElement("head")
    with pytest.raises(xmlprinter.WellFormedError):
        new_xml.endDocument(autoclose=False)


#
# Test some features
#


def test_xml_declaration():
    fp = io.BytesIO()
    xml = xmlprinter.xmlprinter(fp)
    xml.startDocument()
    xml.notationDecl(
        "html",
        "-//W3C//DTD XHTML 1.1//EN",
        "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd",
    )
    xml.startElement(
        "html",
        {
            'xmlns': "http://www.w3.org/1999/xhtml",
            'xml:lang': "en-us",
        },
    )
    xml.data("\n")
    xml.endDocument()

    lines = fp.getvalue().decode("utf-8").splitlines()

    assert lines[0] == '<?xml version="1.0" encoding="UTF-8"?>'
    assert lines[1] == "<!DOCTYPE %s>" % " ".join((
        "html PUBLIC",
        '"-//W3C//DTD XHTML 1.1//EN"',
        '"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd"',
    ))
    assert lines[2] == (
        '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en-us">'
    )


def test_data_mode():
    """ test data mode - automatically adds newlines. """
    fp = io.BytesIO()
    xml = xmlprinter.xmlprinter(fp, data_mode=True)
    xml.startDocument()
    xml.startElement("data")
    xml.startElement("value")
    xml.data("example")
    xml.endElement()
    xml.emptyElement("attrs", {'foo': "3"})
    xml.startElement("attrs", {'foo': "1"})
    xml.endElement()
    xml.endDocument()
    assert fp.getvalue().decode("utf-8") == textwrap.dedent(
        """
        <?xml version="1.0" encoding="UTF-8"?>

        <data>
        <value>example</value>
        <attrs foo="3"/>
        <attrs foo="1">
        </attrs>
        </data>
        """
    ).lstrip()


def test_indent():
    """ test indenting. """
    fp = io.BytesIO()
    xml = xmlprinter.xmlprinter(fp, data_mode=True, indent_level=2)
    xml.startDocument()
    xml.startElement("data")
    xml.startElement("value")
    xml.emptyElement("attrs", {'foo': "3"})
    xml.startElement("attrs", {'foo': "1"})
    xml.endElement()
    xml.endDocument()
    assert fp.getvalue().decode("utf-8") == textwrap.dedent(
        """
        <?xml version="1.0" encoding="UTF-8"?>

        <data>
          <value>
            <attrs foo="3"/>
            <attrs foo="1">
            </attrs>
          </value>
        </data>
        """
    ).lstrip()


#
# Test some encoding stuff
#


def test_write_bytestring():
    """ test decoding of input bytestrings with input_encoding. """
    fp = io.BytesIO()
    xml = xmlprinter.xmlprinter(fp, input_encoding="latin-1")
    xml.startDocument(encoding="UTF-8")
    xml.startElement("data")
    xml.data("\n")

    # Add a latin-1 bytestring value
    xml.startElement("value")
    xml.data("Blåbærøl".encode("latin-1"))
    xml.endElement()
    xml.data("\n")

    # Add a unicode value
    xml.startElement("value")
    xml.data("Blåbærsaft")
    xml.endElement()
    xml.data("\n")

    xml.endDocument()
    assert fp.getvalue().decode("utf-8") == textwrap.dedent(
        """
        <?xml version="1.0" encoding="UTF-8"?>
        <data>
        <value>Blåbærøl</value>
        <value>Blåbærsaft</value>
        </data>
        """
    ).lstrip()


def test_write_encoding_strict():
    fp = io.BytesIO()
    xml = xmlprinter.xmlprinter(fp)
    xml.startDocument(encoding="ISO8859-1")
    xml.startElement("data")
    xml.startElement("value")
    xml.data("\n")
    with pytest.raises(UnicodeError):
        xml.data("3 \N{OHM SIGN} (ohm)")


def test_write_encoding_replace():
    fp = io.BytesIO()
    xml = xmlprinter.xmlprinter(fp, encoding_errors="replace")
    xml.startDocument(encoding="ISO8859-1")
    xml.startElement("data")
    xml.startElement("value")
    xml.data("\n")
    xml.data("3 \N{OHM SIGN} (ohm)")
    xml.data("\n")
    xml.endDocument()
    assert fp.getvalue().decode("latin-1") == textwrap.dedent(
        """
        <?xml version="1.0" encoding="ISO8859-1"?>
        <data><value>
        3 ? (ohm)
        </value></data>
        """
    ).lstrip()
