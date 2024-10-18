# -*- coding: utf-8 -*-
#
# Copyright 2024 University of Oslo, Norway
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
Simple RFC-2046 content-type/mime-type parser.

The main purpose behind having a mime-type parser, is the ability to extract a
`charset` parameters for decoding "text/plain" data:

::
    mime_type = MimeType.from_string(obj.headers['content-type'])
    text = obj.body.decode(mime_type.parameters.get("charset", "ascii"))

This code is inspired by *python-mimeparse* - i.e. re-using the `cgi` module
parser functions.  This parser does *not* support comments, as defined in
RFC-2045 and RFC-822.

Newer versions of Python implement a perfectly good parser in
:mod:`email.headerregistry`.  We may want to use the
:class:`email.headerregistry.ContentTypeHeader` to parse the mime-type value on
Python >= 3.6.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import six


def _parseparam(s):
    """
    Parse a mime-header parameter list.

    This is a copy of :mod:`cgi._parseparam`, which has been deprecated in
    newer versions of Python.
    """
    while s[:1] == ';':
        s = s[1:]
        end = s.find(';')
        while end > 0 and (s.count('"', 0, end) - s.count('\\"', 0, end)) % 2:
            end = s.find(';', end + 1)
        if end < 0:
            end = len(s)
        f = s[:end]
        yield f.strip()
        s = s[end:]


def _parse_header(line):
    """
    Parse a content-type like header.

    This is a copy of :mod:`cgi.parse_header`, which has been deprecated in
    newer versions of Python.
    """
    parts = _parseparam(';' + line)
    key = next(parts)
    pdict = {}
    for p in parts:
        i = p.find('=')
        if i >= 0:
            name = p[:i].strip().lower()
            value = p[i + 1:].strip()
            if len(value) >= 2 and value[0] == value[-1] == '"':
                value = value[1:-1]
                value = value.replace('\\\\', '\\').replace('\\"', '"')
            pdict[name] = value
    return key, pdict


def parse_mime_type(value):
    """
    Parse mime-type into its component parts.

    >>> parse_mime_type("text/plain; charset=utf-8")
    ('text', 'plain', {'charset': 'utf-8'})

    :param str value: a mime-type string
    :returns tuple: a tuple with (type, subtype, parameters)
    :raises ValueError: If the input value is not a valid mime-type
    """
    try:
        c_type, params = _parse_header(value)
        m_type, m_subtype = [p.strip() for p in c_type.split("/")]
    except Exception:
        raise ValueError("invalid mime type: " + repr(value))

    if not m_type and m_subtype:
        raise ValueError("invalid mime type: " + repr(value))

    return (m_type, m_subtype, params)


# Special RFC-2045 chars that needs quoting
TSPECIALCS = "()<>@,;:\\\"/[]?="


def quote_string(value):
    """
    Quote a parameter string value if needed.

    This formats a RFC-822 quoted-string with TSPECIALS from RFC-2045
    """
    if not value or " " in value or any(ch in value for ch in TSPECIALCS):
        # We must quote
        value = value.replace("\\", "\\\\")
        value = value.replace("\"", "\\\"")
        value = '"' + value + '"'
    return value


@six.python_2_unicode_compatible
class MimeType(object):
    """ Mime type object. """

    def __init__(self, media_type, media_subtype, parameters=None):
        # "The type, subtype, and parameter names are not case sensitive."
        self.media_type = media_type.lower()
        self.media_subtype = media_subtype.lower()
        self.parameters = {}
        for attr, value in (parameters or {}).items():
            self.parameters[attr.lower()] = value

    @property
    def content_type(self):
        return "{media_type}/{media_subtype}".format(
            media_type=self.media_type,
            media_subtype=self.media_subtype,
        )

    @classmethod
    def from_string(cls, value):
        media_type, media_subtype, parameters = parse_mime_type(value)
        return cls(media_type, media_subtype, parameters)

    def __str__(self):
        # "The ordering of parameters is not significant."
        params = [
            "{}={}".format(attr, quote_string(value))
            for attr, value in sorted(self.parameters.items())
        ]
        return "; ".join([self.content_type] + params)

    def __repr__(self):
        return "<MimeType {}>".format(six.text_type(self))
