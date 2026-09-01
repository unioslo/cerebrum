# -*- coding: utf-8 -*-
#
# Copyright 2018-2026 University of Oslo, Norway
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
r"""
CSV utilities and compatibility classes.

Provides unicode-compatible wrappers for :mod:`csv` writers, and defines a
standard Cerebrum CSV dialect.


Unicode support
================
The standard :mod:`csv` module deals with bytestrings on Python 2, but unicode
on Python 3.  The writers in this module provide a compatibility layer that
works with unicode text streams on both versions.

>>> stream = io.StringIO()  # text stream
>>> writer = UnicodeWriter(stream)


The Cerebrum Dialect
=====================
:class:`.CerebrumDialect` is the preferred CSV dialect for Cerebrum exports.
Importing this module registers it under the name "cerebrum".

>>> with io.StringIO() as stream:
...     writer = UnicodeWriter(stream, dialect=CerebrumDialect)
...     writer.writerow(["foo", 3, "with spaces", "literal;semicolon"])
...     stream.getvalue()
'foo;3;with spaces;literal\\;semicolon\n'

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import csv
import logging
import io

import six

logger = logging.getLogger(__name__)


class _CsvWriter(object):
    """ Wrapper for csv.writer. """

    writer_class = csv.writer

    def __init__(self, stream, *args, **kwargs):
        if self.writer_class is None:
            raise NotImplementedError("writer_class not set")
        self.writer = self.writer_class(stream, *args, **kwargs)

    def writerow(self, row):
        self.writer.writerow(row)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


class _DictWriter(_CsvWriter):
    """ Wrapper for csv.DictWriter. """

    writer_class = csv.DictWriter

    def writeheader(self):
        row = dict(zip(self.writer.fieldnames, self.writer.fieldnames))
        self.writerow(row)


class _Py2UnicodeSupport(_CsvWriter):
    """ Unicode-compatible CSV writer base class.

    Adapted from https://docs.python.org/2/library/csv.html
    """
    # Encoding to use in the writer_class
    transcode = 'utf-8'

    def __init__(self, stream, *args, **kwargs):
        self.queue = io.BytesIO()
        self.stream = stream
        super(_Py2UnicodeSupport, self).__init__(self.queue, *args, **kwargs)

    def convert_row(self, row):
        raise NotImplementedError("needs writer-class specific conversion")

    def writerow(self, row):
        # Write encoded output to queue
        raw_csv_row = self.convert_row(row)
        self.writer.writerow(raw_csv_row)
        data = self.queue.getvalue()

        # decode the encoded queue data
        data = data.decode(self.transcode)
        self.stream.write(data)

        # reset the queue
        self.queue.truncate(0)
        self.queue.seek(0)


if six.PY2:
    class _BaseWriter(_Py2UnicodeSupport):
        """ Unicode-compatible CSV writer based on ``csv.writer``.  """

        def convert_row(self, row):
            return [six.text_type(s).encode(self.transcode)
                    for s in row]

    class _BaseDictWriter(_DictWriter, _Py2UnicodeSupport):
        """ Unicode-compatible CSV writer based on ``csv.DictWriter``.  """

        def convert_row(self, row):
            return dict(
                (k, six.text_type(v).encode(self.transcode))
                for k, v in row.items())

else:
    _BaseWriter = _CsvWriter
    _BaseDictWriter = _DictWriter


class UnicodeWriter(_BaseWriter):
    """
    Simplified CSV writer with unicode support.

    This class adds Unicode support to :func:`csv.writer` on Python 2.

    .. py:method:: writerow(row)

       Write a single row as a CSV record.

       :type row: list or tuple

    .. py:method:: writerows(rows)

       Write an iterable of rows.

    """
    pass


class UnicodeDictWriter(_BaseDictWriter):
    """
    Simplified CSV dict writer with unicode support.

    This class adds Unicode support to :class:`csv.DictWriter` on Python 2.

    .. py:method:: writeheader()

       Write a CSV header with field names.

    .. py:method:: writerow(row)

       Write a single row as a CSV record.

       :type row: dict

    .. py:method:: writerows(rows)

       Write an iterable of rows.

    """
    pass


class CerebrumDialect(csv.Dialect):
    """ Default Cerebrum dialect.  """

    delimiter = str(";")
    """ field delimiter (semicolon). """

    escapechar = str("\\")
    """ escape character (backslash). """

    lineterminator = str("\n")
    """ line termination (newline). """

    quoting = csv.QUOTE_NONE
    """ field quoting (no quoting). """


csv.register_dialect('cerebrum', CerebrumDialect)
