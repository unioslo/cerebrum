# -*- coding: utf-8 -*-
#
# Copyright 2018-2024 University of Oslo, Norway
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
""" csv utilities. """
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
    """ CSV writer wrapper class. """

    # Base class for formatting the csv bytestring
    writer_class = None

    def __init__(self, stream, *args, **kwargs):
        if self.writer_class is None:
            raise NotImplementedError("writer_class not set")
        self.writer = self.writer_class(stream, *args, **kwargs)

    def writerow(self, row):
        self.writer.writerow(row)

    def writerows(self, rows):
        for row in rows:
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
    class UnicodeWriter(_Py2UnicodeSupport):
        """ Unicode-compatible CSV writer based on ``csv.writer``.  """

        writer_class = csv.writer

        def convert_row(self, row):
            return [six.text_type(s).encode(self.transcode)
                    for s in row]

    class UnicodeDictWriter(_Py2UnicodeSupport):
        """ Unicode-compatible CSV writer based on ``csv.DictWriter``.  """

        writer_class = csv.DictWriter

        def convert_row(self, row):
            return dict(
                (k, six.text_type(v).encode(self.transcode))
                for k, v in row.items())

        def writeheader(self):
            row = dict(zip(self.writer.fieldnames, self.writer.fieldnames))
            self.writerow(row)

else:
    class UnicodeWriter(_CsvWriter):
        """ Unicode-compatible CSV writer based on ``csv.writer``.  """
        writer_class = csv.writer

    class UnicodeDictWriter(_CsvWriter):
        """ Unicode-compatible CSV writer based on ``csv.DictWriter``.  """
        writer_class = csv.DictWriter

        def writeheader(self):
            self.writer.writeheader()


class CerebrumDialect(csv.Dialect):
    """
    Describe the default Cerebrum dialect.

    The dialect does *not* use quoting, and only applies a backslash escape
    char to the default delimiter, ';'.
    """
    delimiter = str(";")
    escapechar = str("\\")
    lineterminator = str("\n")
    quoting = csv.QUOTE_NONE


csv.register_dialect('cerebrum', CerebrumDialect)
