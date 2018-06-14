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
import io

import six


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
