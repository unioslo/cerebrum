# -*- coding: utf-8 -*-
#
# Copyright 2018 University of Oslo, Norway
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

from __future__ import absolute_import

import abc
import csv
import logging
import io

import six

logger = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class _UnicodeSupport(object):
    """ Unicode-compatible CSV writer base class.

    Adapted from https://docs.python.org/2/library/csv.html
    """

    # Base class for formatting the csv bytestring
    writer_class = None

    # Encoding to use in the writer_class
    transcode = 'utf-8'

    def __init__(self, stream, *args, **kwargs):
        self.queue = io.BytesIO()
        self.stream = stream
        if self.writer_class is None:
            raise NotImplementedError("writer_class not set")
        self.writer = self.writer_class(self.queue, *args, **kwargs)

    @abc.abstractmethod
    def convert_row(self, row):
        pass

    def writerow(self, row):
        # Write encoded output to queue
        self.writer.writerow(self.convert_row(row))
        data = self.queue.getvalue()

        # Read formatted CSV data from queue, and write to stream
        data = data.decode(self.transcode)
        self.stream.write(data)
        self.queue.truncate(0)
        self.queue.seek(0)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


class UnicodeWriter(_UnicodeSupport):
    """ Unicode-compatible CSV writer based on ``csv.writer``.  """

    writer_class = csv.writer

    def convert_row(self, row):
        return [six.text_type(s).encode(self.transcode)
                for s in row]


class UnicodeDictWriter(_UnicodeSupport):
    """ Unicode-compatible CSV writer based on ``csv.DictWriter``.  """

    writer_class = csv.DictWriter

    def convert_row(self, row):
        return dict(
            (k, six.text_type(v).encode(self.transcode))
            for k, v in row.items())

    def writeheader(self):
        return self.writer.writeheader()


class CerebrumDialect(csv.Dialect):
    """
    Describe the default Cerebrum dialect.

    The dialect does *not* use quoting, and only applies a backslash escape
    char to the default delimiter, ';'.
    """
    delimiter = ';'
    escapechar = '\\'
    lineterminator = '\n'
    quoting = csv.QUOTE_NONE


csv.register_dialect('cerebrum', CerebrumDialect)


def _read_and_map_csv(filename, csv_reader, csv_transform, **kwargs):
    """
    Create a csv file iterator.

    This function wraps csv.reader classes with some error handling and
    logging.

    """
    logger.info("Reading csv file=%r", filename)
    count = 0
    with open(filename, mode='r') as f:
        reader = csv_reader(f, **kwargs)
        for count, record in enumerate(reader, 1):
            try:
                yield csv_transform(record)
            except Exception:
                logger.error("Unable to process record #%d (file=%r, line=%r)",
                             count, filename, reader.line_num)
                raise
    logger.info("Read %d records from file=%r", count, filename)


def read_csv_dicts(filename, encoding, delimiter):
    """
    Wrapper for reading csv files with csv.DictReader.

    This function wraps csv.DictReader to add unicode support and debugging.

    :param filename: csv file
    :param encoding: csv file encoding
    :param delimiter: csv field separator

    :rtype: generator
    :returns:
        A generator that yields a dict for each entry in the CSV file.
    """
    def transform(record):
        return dict(
            (k.decode(encoding),
             v.decode(encoding) if v is not None else None)
            for k, v in record.items())

    return _read_and_map_csv(
        filename=filename,
        csv_reader=csv.DictReader,
        csv_transform=transform,
        delimiter=delimiter.encode(encoding))


def read_csv_tuples(filename, encoding, delimiter):
    """
    Wrapper for reading csv files with csv.reader.

    This function wraps csv.reader to add unicode support and debugging.

    :param filename: csv file
    :param encoding: csv file encoding
    :param delimiter: csv field separator

    :rtype: generator
    :returns:
        A generator that yields a tuple for each entry in the CSV file.
    """
    def transform(record):
        return tuple((value.decode(encoding) for value in record))

    return _read_and_map_csv(
        filename=filename,
        csv_reader=csv.reader,
        csv_transform=transform,
        delimiter=delimiter.encode(encoding))
