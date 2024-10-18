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
Simple RFC-2046 MIME Content-Type parser.

The main purpose behind having a content-type parser, is the ability to extract
a `charset` parameter for decoding "text/plain" data:

::
    charset = get_charset(obj.headers['content-type'])
    text = obj.body.decode(charset)

The MIME specification is also used for e.g. the HTTP Content-Type header and
the AMQP content-type message property.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import sys

import six


def _extract_media_type(value):
    """ Extract media-type/media-subtype from a content-type value. """
    ct = value.split(";")[0]
    try:
        main, sub = [p.lower().strip() for p in ct.split("/")]
    except ValueError:
        raise ValueError("invalid mime type: " + repr(value))
    if not all((main, sub)):
        raise ValueError("invalid mime type: " + repr(value))
    return main, sub


if sys.version_info >= (3, 6):
    from email import headerregistry

    class _Header(headerregistry.ContentTypeHeader, headerregistry.BaseHeader):
        pass

    def _extract_params(value):
        """ Extract parameters from a content-type value. """
        try:
            result = _Header.value_parser(value)
        except Exception as e:
            raise ValueError("invalid mime type: %s (%s)" % (repr(value), e))
        return {k.lower(): v for k, v in (result.params or []) if k and v}

else:
    from email import message

    def _remove_comment(value):
        r"""
        Remove comment part from property values.

        This is a hacky fix for missing comment support in Python 2.

        This isn't a generic fix, because property values *could* potentially
        have values that looks like comments, but aren't (if quoted properly).
        E.g. the content-type ``text/plain; charset="utf-8" (Plain Text)``,
        would have params = [('charset', '"utf-8" (Plain Text)')]``, but
        *should* have ``[('charset', 'utf-8')]``.

        However, ``application/x-foo bar="\"utf-8\" (Plain Text)"`` is a valid
        content-type where the properties are actually
        ``[('bar', '"utf-8" (Plain Text)')]``
        """
        if " (" in value:
            value = value.split(" (")[0].rstrip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
        return value

    def _extract_params(value):
        """ Extract parameters from a content-type value. """
        try:
            msg = message.Message()
            msg['content-type'] = value
            param_list = msg.get_params() or []
            return {k: _remove_comment(v)
                    for k, v in param_list[1:]
                    if k and v}
        except Exception as e:
            raise ValueError("invalid mime type: %s (%s)" % (repr(value), e))


def parse_mime_type(value):
    """
    Parse mime-type into its component parts.

    >>> parse_mime_type("text/plain; charset=utf-8")
    ('text', 'plain', {'charset': 'utf-8'})

    :param str value: a mime-type string
    :returns tuple: a tuple with (type, subtype, parameters)
    :raises ValueError: If the input value is not a valid mime-type
    """
    m_type, m_subtype = _extract_media_type(value)
    params = _extract_params(value)
    return m_type, m_subtype, params


def get_charset(value, default=None):
    """
    Exctract 'charset' from a mime-type like string.

    >>> get_charset("text/plain; charset=utf-8")
    "utf-8"
    >>> get_charset("foo", default="latin-1")
    "latin-1"

    :param str value: a mime-type string
    :param default: a default value if no valid charset is given
    :returns: the charset, or the default value if not charset is found
    """
    try:
        _, _, params = parse_mime_type(value)
    except ValueError:
        params = {}
    return params.get('charset') or default


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
