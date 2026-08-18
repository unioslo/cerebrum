# -*- coding: utf-8 -*-
#
# Copyright 2023-2026 University of Oslo, Norway
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
Get input or output file streams for scripts.

This module provides helpers and file contexts for reading from, or writing to
file streams.  This module gives a bit better control on whether you get a byte
stream or text stream across Python 2 and Python 3, and adds basic support for
using stdin/stdout rather than opening a new file stream.

These helpers are typically used in scripts, where input or output files are
given as command line options.

Example use:
::

    with get_input_context(input_file, encoding="utf-8") as f:
        input_text = f.read()

    # process input and generate output
    output_bytes = input_text.encode("utf-16")

    with get_output_context(output_file, encoding=None) as f:
        f.write(output_bytes)

    # If both `input_file` and `output_file` is "-", then the script will
    # read from stdin and write to stdout.
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

# TODO: This should probably be removed
DEFAULT_ENCODING = "utf-8"
"""
Default file encoding - not used.
"""

DEFAULT_STDIN_NAME = "-"
"""
Default filename for opening stdin.

If this name is provided as a filename to open in :func:`.get_input_context` or
:func:`.open_input_stream`, then :data:`sys.stdin` will be used.  Support for
stdin, or the name for stdin can be overridden in these functions.
"""

DEFAULT_STDOUT_NAME = "-"
"""
Default filename for opening stdout.

If this name is provided as a filename to open in :func:`.get_output_context`
or :func:`.open_output_stream`, then :data:`sys.stdout` will be used.  Support
for stdout, or the name for stdout can be overridden in these functions.
"""

DEFAULT_STDERR_NAME = None
"""
Default filename for opening stderr.

Support for opening stderr is disabled by default, but can be overridden with
a name for stderr in :func:`.get_output_context` and
:func:`.open_output_stream`.

If a custom stderr name is provided for those functions, then a filename with
that name will open :data:`sys.stderr`.
"""

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
    bytestream = sys.stderr.buffer if _PY3 else sys.stderr
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
    Open a readable byte or text stream.

    :param filename: file to read, or *stdin* to get stdin
    :param encoding: encoding to use, or ``None`` to get a byte stream
    :param stdin: filename value that returns stdin (use ``None`` to disable)
    """
    stream, close = _open_input_stream(filename, encoding, stdin)
    return stream


@contextlib.contextmanager
def get_input_context(filename, encoding=None, stdin=DEFAULT_STDIN_NAME):
    """
    Get a context with a byte or text stream for reading.

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
    Open a writable byte or text stream.

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
    Get a context with a byte or text stream for writing.

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
