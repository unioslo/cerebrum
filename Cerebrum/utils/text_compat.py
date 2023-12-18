# coding: utf-8
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
# Copyright 2002-2015 University of Oslo, Norway
"""
This module contains generic PY2/PY3 text compatibility functions.

This module is temporary, and is only in place to aid the transition from
Python 2.7 to Python 3.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import six


DEFAULT_ENCODING = "utf-8"


def to_str(value, encoding=DEFAULT_ENCODING):
    """
    Like str(value), but with implicit encoding/decoding.

    :param value:
        Value to turn into a native `str`

    :param encoding:
        Encoding to use for implicit encoding/decoding.

        On PY2: encoding will be used to encode *value* if it's a unicode text
        On PY3: encoding will be used to decode *value* if it's a bytestring

    :rtype: str
    """
    if isinstance(value, str):
        # already a native str
        return value

    if isinstance(value, bytes):
        # PY3-bytes (PY2-bytes handled in first if-test)
        return value.decode(encoding)

    if isinstance(value, six.text_type):
        # PY2-uniode (PY3-unicode handled in first if-test)
        return value.encode(encoding)

    # not str-like
    return str(value)


def to_text(value, encoding=DEFAULT_ENCODING):
    """
    Like six.text_type(value), but with implicit decoding.

    :param value:
        Value to turn into text.

    :param encoding:
        Encoding to use for implicit decoding if the *value* is a bytestring.

    :rtype: str
    """
    if isinstance(value, six.text_type):
        return value
    if isinstance(value, bytes):
        return value.decode(encoding)
    # not str-like
    return six.text_type(value)


def to_bytes(value, encoding=DEFAULT_ENCODING):
    """
    Like str(value), but with result in `bytes`.

    :param value:
        Value to turn into `bytes`

    :param encoding:
        Encoding to use for implicit encoding if the *value* is a unicode text.

    :rtype: str
    """
    if isinstance(value, bytes):
        return value

    # ensure string-like
    if not isinstance(value, six.string_types):
        # to native string
        value = str(value)

    if isinstance(value, six.text_type):
        return value.encode(encoding)
    return value
