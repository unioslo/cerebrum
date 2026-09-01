# -*- coding: utf-8 -*-
#
# Copyright 2024-2026 University of Oslo, Norway
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
Simple RFC-2046 mime-type parsing and formatting.

The mime-type format is typically used in ``Content-Type`` headers and fields
when transporting data, e.g. in the HTTP Content-Type header and the AMQP
content-type message property.

The main use case for this module is to help extracting a *charset* parameter
for decoding *text/plain* data:
::

    charset = get_charset(obj.headers['content-type'], default="latin-1")
    text = obj.body.decode(charset)

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

        This is a hacky fix to remove comments from parameters, as the only
        proper parser in the Python 2 standard library fails to handle comments
        correctly.

        Without this hack, the content-type value ``text/plain; charset="utf-8"
        (Plain Text)``, would have charset ``'"utf-8" (Plain Text)'``, when in
        reality it *should* have charset ``'utf-8'``.

        Parameter values can contain values that look like comments, but aren't
        (if quoted properly).  This fix will incorrectly remove those
        comment-like substrings from the actual parameter value.  E.g.
        ``text/plain; charset="\"utf-8\" (Plain Text)"`` is valid content-type
        syntax where the charset value is actually ``'"utf-8" (Plain Text)'``.
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
    Parse a mime-type string into its component parts.

    >>> parse_mime_type("text/plain; charset=utf-8")
    ('text', 'plain', {'charset': 'utf-8'})

    :param str value: a mime-type string

    :rtype: tuple[str, str, dict]
    :returns: a tuple with (media type, media subtype, parameters)

    :raises ValueError: if the input value is not properly formatted
    """
    m_type, m_subtype = _extract_media_type(value)
    params = _extract_params(value)
    return m_type, m_subtype, params


def get_charset(value, default=None):
    """
    Extract 'charset' from a mime-type string.

    >>> get_charset("text/plain; charset=utf-8")
    "utf-8"
    >>> get_charset("foo", default="latin-1")
    "latin-1"

    :param str value: a mime-type string
    :param default: a default value if no charset is given (see RFC-6657)

    :returns: the charset, or the default value if no charset is found
    """
    try:
        _, _, params = parse_mime_type(value)
    except ValueError:
        params = {}
    return params.get('charset') or default


TSPECIALCS = "()<>@,;:\\\"/[]?="
""" RFC-2045 special characters (requires quoting). """


def quote_string(value):
    """
    Quote a parameter string value if needed.

    This formats an RFC-822 quoted-string with TSPECIALS from RFC-2045.

    >>> quote_string("utf-8")
    'utf-8'
    >>> quote_string("foo; bar;")
    '"foo; bar;"'
    """
    if not value or " " in value or any(ch in value for ch in TSPECIALCS):
        # We must quote
        value = value.replace("\\", "\\\\")
        value = value.replace("\"", "\\\"")
        value = '"' + value + '"'
    return value


@six.python_2_unicode_compatible
class MimeType(object):
    """ Object representation of a mime-type. """

    def __init__(self, media_type, media_subtype, parameters=None):
        # We enforce lowercase for the media type, for consistency.  RFC-2046:
        # "The type, subtype, and parameter names are not case sensitive."
        self.media_type = media_type.lower()
        self.media_subtype = media_subtype.lower()
        self.parameters = {}
        for attr, value in (parameters or {}).items():
            self.parameters[attr.lower()] = value

    @property
    def content_type(self):
        """ The media type and subtype as 'type/subtype'. """
        # TODO: This property should probably be renamed to `media`
        return "{media_type}/{media_subtype}".format(
            media_type=self.media_type,
            media_subtype=self.media_subtype,
        )

    @classmethod
    def from_string(cls, value):
        """ Parse a mime-type string into a MimeType object. """
        media_type, media_subtype, parameters = parse_mime_type(value)
        return cls(media_type, media_subtype, parameters)

    def __str__(self):
        """ str(MimeType) -> mime-type string. """
        # We sort the values for consistent results.  RFC-2046: "The ordering
        # of parameters is not significant."
        params = [
            "{}={}".format(attr, quote_string(value))
            for attr, value in sorted(self.parameters.items())
        ]
        return "; ".join([self.content_type] + params)

    def __repr__(self):
        """ repr(MimeType) -> object representation. """
        return "<MimeType {}>".format(six.text_type(self))


def format_mime_type(media_type, media_subtype, parameters=None):
    """ Format a mime-type string. """
    return six.text_type(MimeType(media_type, media_subtype, parameters))
