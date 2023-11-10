# -*- coding: utf-8 -*-
#
# Copyright 2017-2023 University of Oslo, Norway
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
File writer objects.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
)
import codecs
import locale


class CerelogStreamWriter(codecs.StreamWriter, object):
    """ Convert all input to specified charsets.

    The purpose of this class is to allow:

    stream.write('foo')
    stream.write('foo æøå')
    stream.write(unicode('foo'))
    stream.write(unicode('foo æøå', 'latin1'))

    ... so that the client code does not have to care about the
    encodings, regardless of the encodings specified in logging.ini.

    The unicode objects can be output quite easily. The problem arises with
    non-ascii str objects. We have no way of *knowing* their exact encoding,
    and some guesswork is involved in outputting the strings.

    """

    def __init__(self, stream, errors="strict"):
        super(CerelogStreamWriter, self).__init__(stream, errors)

        # What's the expected encoding for strings?
        self.incoming_encodings = list()
        for x in (locale.getpreferredencoding(),
                  "utf-8",
                  "iso-8859-1",
                  "windows-1252"):
            if x.lower() not in self.incoming_encodings:
                self.incoming_encodings.append(x.lower())

    def write(self, obj):
        """Force conversion to self.encoding."""

        # We force strings to unicode, so we won't have to deal with encoding
        # crap later.
        if self.incoming_encodings and isinstance(obj, str):
            # The problem at this point is: what is the encoding in which obj
            # is represented? There is no way we can know this for sure, since
            # we have no idea what the environment of python is...
            for encoding in self.incoming_encodings:
                try:
                    obj = obj.decode(encoding)
                    break
                except UnicodeError:
                    pass

            # IVR 2008-05-16 TBD: What do we do here, if obj is NOT unicode?

        data, consumed = self.encode(obj, self.errors)
        self.stream.write(data)

    def writelines(self, lines):
        """"Write concatenated list of strings."""
        self.write(''.join(lines))
