# -*- coding: utf-8 -*-
#
# Copyright 2020-2024 University of Oslo
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
Bofhd uses XML-RPC over HTTP to communicate with clients.

This module implements some protocol-specific methods, like translating
exceptions to XMLRPC faults.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import collections
import warnings

import six
from six.moves import xmlrpc_client

from Cerebrum.modules.bofhd.errors import (
    CerebrumError,
    ServerRestartedError,
    SessionExpiredError,
    UnknownError,
)
from Cerebrum.utils import text_utils


def dumps(obj):
    """Serializes an XML-RPC response."""
    if isinstance(obj, Exception):
        code, message = _format_xmlrpc_fault(obj)
        fault = xmlrpc_client.Fault(code, message)
        return xmlrpc_client.dumps(fault, methodresponse=True)
    else:
        payload = sanitize(obj)
        return xmlrpc_client.dumps((payload,), methodresponse=True)


def loads(s):
    """
    Deserializes an XML-RPC request,
    returning a tuple of (`method`, `params`).
    """
    params, method = xmlrpc_client.loads(s)
    return method, params


def sanitize(obj):
    """
    Sanitizes strings in arbitrary Python objects for display in
    terminal emulators.

    Not all database values in Cerebrum have been sanitised prior
    to insertion and may therefore contain code points that are
    harmful to display in a terminal emulator.

    One example is "abc\x08" which effectively causes data corruption
    because the last code point (backspace) deletes the last character
    and causes it to render as "ab".  Further, certain control
    sequence characters cause the XML-RPC encoding used by bofhd
    to break.

    This will remove all harmful control sequence characters in all
    string values that are not used for purposes of layout, such
    as tabular, carriage return, and line feed.
    """
    if isinstance(obj, bytes):
        obj = _ensure_unicode(obj)

    if isinstance(obj, six.text_type):
        return text_utils.strip_control_characters(obj, exclude="\t\r\n")
    elif isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    elif isinstance(obj, collections.Iterable):
        return [sanitize(x) for x in obj]
    return obj


def _format_xmlrpc_fault(exc):
    code = 2
    err_type = six.text_type(type(exc).__name__)
    if isinstance(exc, CerebrumError):
        code = 1
        # include module name in CerebrumError and subclasses
        if type(exc) in (
            ServerRestartedError,
            SessionExpiredError,
            UnknownError,
        ):
            # client *should* know this
            err_type = "{0.__module__}.{0.__name__}".format(type(exc))
        else:
            # use superclass
            err_type = "{0.__module__}.{0.__name__}".format(CerebrumError)
    return code, "%s:%s" % (err_type, _ensure_unicode(exc))


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
