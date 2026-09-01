# -*- coding: utf-8 -*-
#
# Copyright 2021-2026 University of Oslo, Norway
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
Common HTTP and URL utilities.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from six.moves.urllib.parse import (
    quote_plus as _quote_plus,
    urljoin as _urljoin,
)

from . import text_compat


def safe_path(arg):
    """
    Escape URL path component.

    This function percent-encodes values for safe use in URLs.  Use this
    when inserting user input or arbitrary values into URL paths.

    >>> safe_path('123/something-else')
    '123%2Fsomething-else'
    """
    return text_compat.to_text(_quote_plus(text_compat.to_str(arg)))


def merge_headers(*dicts):
    """
    Merge header dicts without mutating the originals.

    - Headers are matched case-insensitively
    - Later values override earlier ones.
    - Header name casing from the last occurrence is preserved
    - A ``None`` value will omit the header (including earlier values)

    >>> merge_headers({'x-foo': 1, 'x-bar': 2, 'x-baz': 3},
    ...               {'X-Foo': 4, 'X-Baz': None})
    {'X-Foo': 4, 'x-bar': 2}

    """
    # normalized key -> header name mapping
    header_names = dict()

    # normalized key -> header value mapping
    header_values = dict()

    for d in dicts:
        if not d:
            continue
        for k in d:
            nk = str(k).lower()
            header_names[nk] = k
            header_values[nk] = d[k]

    return {
        header_names[nk]: header_values[nk]
        for nk in header_names
        if header_values[nk] is not None
    }


def urljoin(url, *path_components):
    """
    Join URL path components, preserving all parts.

    Unlike :func:`urllib.parse.urljoin` (here: ``_urljoin``), this function
    appends paths rather than replacing the last component:

    >>> _urljoin('https://localhost/foo', 'bar')
    'https://localhost/bar'
    >>> urljoin('https://localhost/foo', 'bar')
    'https://localhost/foo/bar'
    """
    for path in path_components:
        url = _urljoin(url.rstrip('/') + '/', path)
    return url
