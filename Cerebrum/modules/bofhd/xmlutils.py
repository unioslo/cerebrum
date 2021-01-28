# -*- coding: utf-8 -*-
#
# Copyright 2002-2018 University of Oslo, Norway
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

import datetime
import decimal
import warnings
import xmlrpclib

import six
from mx import DateTime

from Cerebrum.utils import date_compat
from Cerebrum.utils.textnorm import UnicodeNormalizer


normalize = UnicodeNormalizer('NFC')


class AttributeDict(dict):
    """Adds attribute access to keys, ie. a['knott'] == a.knott"""
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        self[name] = value


def ensure_unicode(obj):
    """ Ensure string output -> unicode objects. """
    if isinstance(obj, six.text_type):
        return obj
    try:
        return six.text_type(obj)
    except UnicodeError:
        # TODO: Fail hard?
        warnings.warn("invalid unicode: {0}".format(repr(obj)), UnicodeWarning)
        return obj.decode('utf-8', 'replace')


def native_to_xmlrpc(obj):
    """Translate Python objects to XML-RPC-usable structures."""
    if obj is None:
        return ':None'
    elif isinstance(obj, bytearray):
        # TODO: Bytes should also be handled here
        return xmlrpclib.Binary(data=obj)
    elif isinstance(obj, (bytes, six.text_type)):
        if obj.startswith(":"):
            return ensure_unicode(":" + obj)
        return ensure_unicode(obj)
    elif isinstance(obj, (tuple, list)):
        obj_type = type(obj)
        return obj_type([native_to_xmlrpc(x) for x in obj])
    elif isinstance(obj, dict):
        obj_type = type(obj)
        return obj_type([(native_to_xmlrpc(x), native_to_xmlrpc(obj[x]))
                         for x in obj])
    elif isinstance(obj, (int, long, float)):
        return obj
    elif isinstance(obj, decimal.Decimal):
        return float(obj)
    elif isinstance(obj, (xmlrpclib.DateTime, DateTime.DateTimeType)):
        return xmlrpclib.DateTime(tuple([int(i) for i in obj.tuple()]))
    elif isinstance(obj, datetime.date):
        # (datetime.date, datetime.datetime) -> naive datetime -> xmlrpc
        return xmlrpclib.DateTime(date_compat.get_datetime_naive(obj))
    else:
        raise ValueError("Unrecognized parameter type: '{!r}' {!r}".format(
            obj, getattr(obj, '__class__', type(obj))))


def xmlrpc_to_native(obj):
    """Translate XML-RPC-usable structures back to Python objects"""
    # We could have used marshal.{loads,dumps} here,
    # but then the Java client would have trouble
    # encoding/decoding requests/responses.
    if isinstance(obj, basestring):
        if isinstance(obj, bytes):
            obj = six.text_type(obj)
        if obj == ':None':
            return None
        elif obj.startswith(':'):
            return normalize(obj[1:])
        return normalize(obj)
    elif isinstance(obj, (tuple, list)):
        obj_type = type(obj)
        return obj_type([xmlrpc_to_native(x) for x in obj])
    elif isinstance(obj, dict):
        return AttributeDict([(xmlrpc_to_native(x), xmlrpc_to_native(obj[x]))
                              for x in obj])
    elif isinstance(obj, (int, long, float)):
        return obj
    elif isinstance(obj, xmlrpclib.DateTime):
        return DateTime.ISO.ParseDateTime(obj.value)
    elif isinstance(obj, xmlrpclib.Binary):
        return bytearray(obj.data)
    else:
        # unknown type, no need to recurse
        return obj
