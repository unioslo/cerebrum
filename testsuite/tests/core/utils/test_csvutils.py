# coding: utf-8
""" Tests for mod:`Cerebrum.utils.csvutils` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import io

import pytest

from Cerebrum.utils import csvutils


#
# Test abstract class init
#


@pytest.mark.parametrize("cls", (csvutils._CsvWriter,
                                 csvutils._Py2UnicodeSupport))
def test_missing_writer_class(cls):
    """ Missing writer_class should cause NotImplementedError. """

    with pytest.raises(NotImplementedError):
        with io.StringIO() as file_like:
            cls(file_like)


#
# Test UnicodeWriter
#


def test_writer_init():
    with io.StringIO() as file_like:
        csvutils.UnicodeWriter(file_like)
    assert True  # reached without error


#
# The default dialect (csv.excel) uses commas as separators, return + newline
# line endings, and quoting + double quote for escaping.
#
EXAMPLE_ROW = ("blåbærøl", 1, "foo,bar,baz")
EXAMPLE_TEXT = "blåbærøl,1,\"foo,bar,baz\"\r\n"


def test_writer_writerow():
    with io.StringIO() as file_like:
        writer = csvutils.UnicodeWriter(file_like)
        writer.writerow(EXAMPLE_ROW)
        value = file_like.getvalue()
    assert value == EXAMPLE_TEXT


def test_writer_writerows():
    with io.StringIO() as file_like:
        writer = csvutils.UnicodeWriter(file_like)
        writer.writerows([EXAMPLE_ROW] * 3)
        value = file_like.getvalue()
    assert value == EXAMPLE_TEXT * 3


ENCODING = "UTF-8"
BYTES_ROW = ("foo".encode(ENCODING), 1, "blåbærøl".encode(ENCODING))


def test_writer_write_bytestream():
    """ Our UnicodeWriter won't write to a byte stream. """
    with pytest.raises(TypeError):
        with io.BytesIO() as file_like:
            writer = csvutils.UnicodeWriter(file_like)
            writer.writerow(EXAMPLE_ROW)


#
# Test UnicodeDictWriter
#


EXAMPLE_FIELDS = ("foo", "bar", "blåbærøl")
EXAMPLE_HEADER = "foo,bar,blåbærøl\r\n"


def test_dict_writer_init():
    with io.StringIO() as file_like:
        csvutils.UnicodeDictWriter(file_like, EXAMPLE_FIELDS)
    assert True  # reached without error


def test_dictwriter_writeheader():
    with io.StringIO() as file_like:
        writer = csvutils.UnicodeDictWriter(file_like, EXAMPLE_FIELDS)
        writer.writeheader()
        value = file_like.getvalue()
    assert value == EXAMPLE_HEADER


def test_dictwriter_writerow():
    row = dict(zip(EXAMPLE_FIELDS, EXAMPLE_ROW))
    with io.StringIO() as file_like:
        writer = csvutils.UnicodeDictWriter(file_like, EXAMPLE_FIELDS)
        writer.writerow(row)
        value = file_like.getvalue()
    assert value == EXAMPLE_TEXT


#
# Test CerebrumDialect
#


def test_cerebrum_dialect():
    row = ("blåbærøl", 1, "foo;bar;baz")
    expect = "blåbærøl;1;foo\\;bar\\;baz\n"
    with io.StringIO() as file_like:
        writer = csvutils.UnicodeWriter(file_like,
                                        dialect=csvutils.CerebrumDialect)
        writer.writerow(row)
        value = file_like.getvalue()
    assert value == expect
