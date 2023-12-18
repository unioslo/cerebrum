# -*- coding: utf-8 -*-
#
# Copyright 2021 University of Oslo, Norway
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
Common http and url utils.
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
    """ Escape url component.

    >>> safe_path('123/something-else')
    '123%2Fsomething-else'
    """
    return text_compat.to_text(_quote_plus(text_compat.to_str(arg)))


def merge_headers(*dicts):
    """
    Combine a series of header dicts without mutating any of them.

    >>> merge_headers({'X-Foo': 1}, {'x-bar': 2})
    {'X-Foo': 1, 'x-bar': 2}
    >>> merge_headers({'x-foo': 1}, {'X-Foo': 2})
    {'X-Foo': 2}
    >>> merge_headers(None, None, None)
    {}
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

    return {header_names[nk]: header_values[nk]
            for nk in header_names}


def urljoin(url, *path_components):
    """
    A sane urljoin.

    >>> _urljoin('https://localhost/foo', 'bar')
    'https://localhost/bar'

    >>> urljoin('https://localhost/foo', 'bar')
    'https://localhost/foo/bar'
    """
    for path in path_components:
        url = _urljoin(url.rstrip('/') + '/', path)
    return url
