# encoding: utf-8
"""
Unit tests for :mod:`Cerebrum.utils.file_stream`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import codecs
import io
import os
import sys
import shutil
import tempfile

import pytest

from Cerebrum.utils import file_stream


TEXT_SNIPPET = """
Some text snippets from
<https://www.w3.org/2001/06/utf-8-test/UTF-8-demo.html>.
Original by Markus Kuhn, adapted for HTML by Martin Dürst.

Sample text
‾‾‾‾‾‾‾‾‾‾‾
Mathematics:
  ∮ E⋅da = Q,  n → ∞, ∑ f(i) = ∏ g(i), ∀x∈ℝ: ⌈x⌉ = −⌊−x⌋, α ∧ ¬β = ¬(¬α ∨ β),

Greek:
  Σὲ γνωρίζω ἀπὸ τὴν κόψη

Runes:
  ᚻᛖ ᚳᚹᚫᚦ ᚦᚫᛏ ᚻᛖ ᛒᚢᛞᛖ ᚩᚾ ᚦᚫᛗ ᛚᚪᚾᛞᛖ ᚾᚩᚱᚦᚹᛖᚪᚱᛞᚢᛗ ᚹᛁᚦ ᚦᚪ ᚹᛖᛥᚫ

Braille:
  ⡌⠁⠧⠑ ⠼⠁⠒  ⡍⠜⠇⠑⠹⠰⠎ ⡣⠕⠌
""".lstrip()

ENCODING = "utf-8"

BYTE_SNIPPET = TEXT_SNIPPET.encode(ENCODING)

PY3 = (sys.version_info >= (3,))


@pytest.fixture(autouse=True)
def _stdin_snippet(monkeypatch):
    """ Fixture that monkeypatches stdin to always contain *TEXT_SNIPPET*. """
    stream = io.BytesIO(BYTE_SNIPPET)
    if PY3:
        # Py3 - stdin is a text stream by default, so we need to provide both
        # a text stream and the underlying byte stream.
        codec = codecs.lookup(ENCODING)
        stream = codec.streamreader(stream)
        # This is a bit silly, but we need to provide the bytestream as a
        # `buffer` attribute.
        setattr(stream, "buffer", stream.stream)
    monkeypatch.setattr("sys.stdin", stream)


@pytest.fixture(scope='module')
def write_dir():
    """ Fixture that creates a temporary directory for this test module. """
    tempdir = tempfile.mkdtemp()
    yield tempdir
    # `rm -r` the temp-dir after after all tests have completed, to ensure all
    # files are cleared out.
    shutil.rmtree(tempdir)


@pytest.fixture
def new_file(write_dir):
    """ Fixture to get a new temporary filename for use in a test. """
    # Create and remove a temp file.  This generates a name for us, and ensures
    # that the file *can* exist.
    fd, name = tempfile.mkstemp(dir=write_dir)
    os.close(fd)
    os.unlink(name)
    # `name` is now the path to a non-existing tmp-file
    yield name
    # remove the file if the test created it
    if os.path.exists(name):
        os.unlink(name)


@pytest.fixture
def text_file(write_dir):
    """ Fixture to create a file with *TEXT_SNIPPET* as content. """
    fd, name = tempfile.mkstemp(dir=write_dir)
    os.write(fd, BYTE_SNIPPET)
    os.close(fd)
    yield name
    os.unlink(name)


#
# Reading input files
#

def test_input_text_stream(text_file):
    fd = file_stream.open_input_stream(text_file, encoding=ENCODING)
    text = fd.read()
    fd.close()
    assert text == TEXT_SNIPPET


def test_input_byte_stream(text_file):
    fd = file_stream.open_input_stream(text_file, encoding=None)
    text = fd.read()
    fd.close()
    assert text == BYTE_SNIPPET


def test_input_text_context(text_file):
    with file_stream.get_input_context(text_file, encoding=ENCODING) as fd:
        text = fd.read()
    assert fd.closed
    assert text == TEXT_SNIPPET


def test_input_byte_context(text_file):
    with file_stream.get_input_context(text_file, encoding=None) as fd:
        text = fd.read()
    assert fd.closed
    assert text == BYTE_SNIPPET


#
# Reading from stdin
#

def test_stdin_text_stream():
    fd = file_stream.open_input_stream(file_stream.DEFAULT_STDIN_NAME,
                                       encoding=ENCODING)
    text = fd.read()
    assert text == TEXT_SNIPPET


def test_stdin_byte_stream():
    fd = file_stream.open_input_stream(file_stream.DEFAULT_STDIN_NAME,
                                       encoding=None)
    text = fd.read()
    assert text == BYTE_SNIPPET


def test_stdin_text_context():
    with file_stream.get_input_context(file_stream.DEFAULT_STDIN_NAME,
                                       encoding=ENCODING) as fd:
        text = fd.read()

    assert not fd.closed
    assert text == TEXT_SNIPPET


def test_stdin_byte_context():
    with file_stream.get_input_context(file_stream.DEFAULT_STDIN_NAME,
                                       encoding=None) as fd:
        text = fd.read()

    assert not fd.closed
    assert text == BYTE_SNIPPET


#
# Writing output files
#

def _file_contains_snippet(filename):
    """ Check that a file contains the text snippet. """
    with open(filename, 'rb') as f:
        content = f.read()
    return content == BYTE_SNIPPET


def test_output_text_stream(new_file):
    fd = file_stream.open_output_stream(new_file, encoding=ENCODING)
    fd.write(TEXT_SNIPPET)
    fd.close()
    assert _file_contains_snippet(new_file)


def test_output_byte_stream(new_file):
    fd = file_stream.open_output_stream(new_file, encoding=None)
    fd.write(BYTE_SNIPPET)
    fd.close()
    assert _file_contains_snippet(new_file)


def test_output_text_context(new_file):
    with file_stream.get_output_context(new_file, encoding=ENCODING) as fd:
        fd.write(TEXT_SNIPPET)

    assert fd.closed
    assert _file_contains_snippet(new_file)


def test_output_byte_context(new_file):
    with file_stream.get_output_context(new_file, encoding=None) as fd:
        fd.write(BYTE_SNIPPET)

    assert fd.closed
    assert _file_contains_snippet(new_file)


#
# Writing to stdout
#

def test_stdout_text_stream(capsys):
    fd = file_stream.open_output_stream(file_stream.DEFAULT_STDOUT_NAME,
                                        encoding=ENCODING)
    fd.write(TEXT_SNIPPET)
    out, err = capsys.readouterr()
    assert out == TEXT_SNIPPET


def test_stdout_byte_stream(capsys):
    fd = file_stream.open_output_stream(file_stream.DEFAULT_STDOUT_NAME,
                                        encoding=None)
    fd.write(BYTE_SNIPPET)
    out, err = capsys.readouterr()
    assert out == TEXT_SNIPPET


def test_stdout_text_context(capsys):
    with file_stream.get_output_context(file_stream.DEFAULT_STDOUT_NAME,
                                        encoding=ENCODING) as fd:
        fd.write(TEXT_SNIPPET)

    assert not fd.closed
    out, err = capsys.readouterr()
    assert out == TEXT_SNIPPET


def test_stdout_byte_context(capsys):
    with file_stream.get_output_context(file_stream.DEFAULT_STDOUT_NAME,
                                        encoding=None) as fd:
        fd.write(BYTE_SNIPPET)

    assert not fd.closed
    out, err = capsys.readouterr()
    assert out == TEXT_SNIPPET


#
# Some expected errors - not sure we really need to test this?
#
def test_text_to_byte_stream(new_file):
    with file_stream.get_output_context(new_file, encoding=None) as fd:
        # TODO: Do we want to change this somehow in the file context?
        error_type = TypeError if PY3 else UnicodeError
        with pytest.raises(error_type):
            fd.write(TEXT_SNIPPET)

    assert fd.closed


def test_bytes_to_text_stream(new_file):
    with file_stream.get_output_context(new_file, encoding=ENCODING) as fd:
        with pytest.raises(TypeError):
            fd.write(BYTE_SNIPPET)

    assert fd.closed
