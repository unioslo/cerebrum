#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2023 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
"""
Utility to get input or output file streams for scripts.

These streams are typically used for reading input or generating output in
scripts.  This module gives a bit better control on whether you get a byte
stream or text stream across Python 2 and Python 3, and adds basic support for
using stdin/stdout rather than opening a new file stream.

Example use:
::

    with get_input_context(input_file, encoding="utf-8") as f:
        input_text = f.read()

    # process input and generate output
    output_bytes = input_text.encode("utf-16")

    with get_output_context(output_file, encoding=None) as f:
        f.write(output_bytes)

    # If both `input_file` and `output_file` is "-", then the script will
    # read from stdin and and write to stdout.

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import codecs
import contextlib
import io
import logging
import sys

_PY3 = (sys.version_info >= (3,))

DEFAULT_ENCODING = "utf-8"
DEFAULT_STDIN_NAME = "-"
DEFAULT_STDOUT_NAME = "-"
DEFAULT_STDERR_NAME = None

logger = logging.getLogger(__name__)


def _get_stdin(encoding):
    """ Get text or byte access to stdin. """
    bytestream = sys.stdin.buffer if _PY3 else sys.stdin
    if encoding:
        codec = codecs.lookup(encoding)
        return codec.streamreader(bytestream)
    else:
        return bytestream


def _get_stdout(encoding):
    """ Get text or byte access to stdout. """
    bytestream = sys.stdout.buffer if _PY3 else sys.stdout
    if encoding:
        codec = codecs.lookup(encoding)
        return codec.streamwriter(bytestream)
    else:
        return bytestream


def _get_stderr(encoding):
    """ Get text or byte access to stderr. """
    bytestream = sys.stdout.buffer if _PY3 else sys.stderr
    if encoding:
        codec = codecs.lookup(encoding)
        return codec.streamwriter(bytestream)
    else:
        return bytestream


def _open_input_stream(filename, encoding, stdin_symbol):
    if stdin_symbol and filename == stdin_symbol:
        stream = _get_stdin(encoding)
        should_close = False
    else:
        mode = 'r' if encoding else 'rb'
        stream = io.open(filename, mode=mode, encoding=encoding)
        should_close = True
    logger.debug("opened %s as %s stream (encoding=%s): %s",
                 repr(filename), "text" if encoding else "byte",
                 repr(encoding), repr(stream))
    return stream, should_close


def _open_output_stream(filename, encoding, stdout_symbol, stderr_symbol):
    if stdout_symbol and filename == stdout_symbol:
        stream = _get_stdout(encoding=encoding)
        should_close = False
    elif stderr_symbol and filename == stderr_symbol:
        stream = _get_stderr(encoding=encoding)
        should_close = False
    else:
        mode = 'w' if encoding else 'wb'
        stream = io.open(filename, mode=mode, encoding=encoding)
        should_close = True
    logger.debug("opened %s as %s stream (encoding=%s): %s",
                 repr(filename), "text" if encoding else "byte",
                 repr(encoding), repr(stream))
    return stream, should_close


def open_input_stream(filename, encoding=None, stdin=DEFAULT_STDIN_NAME):
    """
    :param filename: file to write, or *stdout*/*stderr* to get a std-stream
    Open a byte or text stream for reading.

    :param filename: file to read, or *stdin* to get stdin
    :param encoding: encoding to use, or ``None`` to get a byte stream
    :param stdin: filename value that returns stdin (use ``None`` to disable)
    """
    stream, close = _open_input_stream(filename, encoding, stdin)
    return stream


@contextlib.contextmanager
def get_input_context(filename, encoding=None, stdin=DEFAULT_STDIN_NAME):
    """
    Get a byte or text stream context for reading.

    This closing file context keeps the stream open if the stream is stdin.

    :param filename: file to read, or *stdin* to get stdin.
    :param encoding: encoding to use, or ``None`` to get a byte stream.
    :param stdin: filename value that returns stdin (use ``None`` to disable)
    """
    stream, close = _open_input_stream(filename, encoding, stdin)
    try:
        yield stream
    finally:
        if stream.closed:
            logger.debug("stream is closed: %s", repr(stream))
        elif close:
            logger.debug("closing stream: %s", repr(stream))
            stream.close()
        else:
            logger.debug("keeping stream open: %s", repr(stream))


def open_output_stream(filename,
                       encoding=None,
                       stdout=DEFAULT_STDOUT_NAME,
                       stderr=DEFAULT_STDERR_NAME):
    """
    Open a byte text stream for writing.

    :param filename: file to write, or a value matching *stdout*/*stderr*
    :param encoding: encoding to use, or ``None`` to get a byte stream.
    :param stdout: filename value that returns stdout (use ``None`` to disable)
    :param stderr: filename value that returns stderr (use ``None`` to disable)
    """
    stream, close = _open_output_stream(filename, encoding, stdout, stderr)
    return stream


@contextlib.contextmanager
def get_output_context(filename,
                       encoding=None,
                       stdout=DEFAULT_STDOUT_NAME,
                       stderr=DEFAULT_STDERR_NAME):
    """
    Get a byte or text stream stream context.

    This closing file context keeps the stream open if the stream is
    stdout/stderr.

    :param filename: file to write, or a value matching *stdout*/*stderr*
    :param encoding: encoding to use, or ``None`` to get a byte stream.
    :param stdout: filename value that returns stdout (use ``None`` to disable)
    :param stderr: filename value that returns stderr (use ``None`` to disable)
    """
    stream, close = _open_output_stream(filename, encoding, stdout, stderr)
    try:
        yield stream
    finally:
        if stream.closed:
            logger.debug("stream is closed: %s", repr(stream))
        elif close:
            logger.debug("closing stream: %s", repr(stream))
            stream.flush()
            stream.close()
        else:
            logger.debug("keeping stream open: %s", repr(stream))
            stream.flush()
