# -*- coding: utf-8 -*-
#
# Copyright 2002-2024 University of Oslo, Norway
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
XML-RPC utilities for bofhd.

This module deals with serializing and de-serializing
XML-RPC data in bofhd.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime
import decimal
import warnings

import six
from six.moves import xmlrpc_client

from Cerebrum.utils import date_compat
from Cerebrum.utils import date as date_utils
from Cerebrum.utils import funcwrap
from Cerebrum.utils.textnorm import UnicodeNormalizer


normalize = UnicodeNormalizer('NFC')

_numerical = six.integer_types + (float,)


class AttributeDict(dict):
    """
    Adds attribute access to keys, ie. a['knott'] == a.knott
    """

    @funcwrap.deprecate("AttributeDict is deprecated")
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    @funcwrap.deprecate("AttributeDict is deprecated")
    def __setattr__(self, name, value):
        self[name] = value


def _ensure_unicode(obj):
    """ Ensure string output -> unicode objects. """
    if isinstance(obj, bytes):
        try:
            return obj.decode("utf-8")
        except UnicodeDecodeError:
            warnings.warn("invalid unicode: {0}".format(repr(obj)),
                          UnicodeWarning)
            return obj.decode("utf-8", "replace")
    return six.text_type(obj)


def native_to_xmlrpc(obj):
    """Translate Python objects to XML-RPC-usable structures."""
    if obj is None:
        return ":None"
    elif isinstance(obj, bytearray):
        # TODO: After upgrading to PY3, byte output should probably also be
        # considered binary data.
        return xmlrpc_client.Binary(data=obj)
    elif isinstance(obj, (bytes, six.text_type)):
        obj = _ensure_unicode(obj)
        if obj.startswith(":"):
            # this allows us to send the actual text ":None" as "::None"
            return ":" + obj
        else:
            return obj
    elif isinstance(obj, (tuple, list)):
        obj_type = type(obj)
        return obj_type([native_to_xmlrpc(x) for x in obj])
    elif isinstance(obj, dict):
        obj_type = type(obj)
        return obj_type([(native_to_xmlrpc(x), native_to_xmlrpc(obj[x]))
                         for x in obj])
    elif isinstance(obj, _numerical):
        return obj
    elif isinstance(obj, decimal.Decimal):
        return float(obj)
    elif isinstance(obj, datetime.date):
        # (datetime.date, datetime.datetime) -> naive datetime -> xmlrpc
        return xmlrpc_client.DateTime(date_compat.get_datetime_naive(obj))
    elif isinstance(obj, xmlrpc_client.DateTime):
        # Why don't we return the object as-is?
        return xmlrpc_client.DateTime(tuple(int(i) for i in obj.tuple()))
    elif date_compat.is_mx_datetime(obj):
        # mx-like -> naive datetime -> xmlrpc
        return xmlrpc_client.DateTime(date_compat.get_datetime_naive(obj))
    else:
        raise ValueError("Unrecognized parameter type: '{!r}' {!r}".format(
            obj, getattr(obj, '__class__', type(obj))))


def xmlrpc_to_native(obj):
    """Translate XML-RPC-usable structures back to Python objects"""
    # We could have used marshal.{loads,dumps} here,
    # but then the Java client would have trouble
    # encoding/decoding requests/responses.
    if isinstance(obj, (six.text_type, bytes)):
        # TODO: After upgrading to PY3, byte input should probably also be
        # considered binary data.
        obj = _ensure_unicode(obj)
        if obj == ":None":
            return None
        if obj.startswith(':'):
            obj = obj[1:]
        return normalize(obj)
    elif isinstance(obj, (tuple, list)):
        obj_type = type(obj)
        return obj_type([xmlrpc_to_native(x) for x in obj])
    elif isinstance(obj, dict):
        return AttributeDict([(xmlrpc_to_native(x), xmlrpc_to_native(obj[x]))
                              for x in obj])
    elif isinstance(obj, _numerical):
        return obj
    elif isinstance(obj, xmlrpc_client.DateTime):
        # This doesn't really happen - all clients send date or datetime as
        # strings in a string type field
        return date_utils.parse_datetime(obj.value)
    elif isinstance(obj, xmlrpc_client.Binary):
        return bytearray(obj.data)
    else:
        # unknown type, no need to recurse
        return obj
