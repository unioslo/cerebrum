# encoding: utf-8
#
# Copyright 2015-2024 University of Oslo, Norway
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
Simple, reuseable function wrappers.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from warnings import warn as _warn
from functools import wraps


def memoize(callobj):
    """
    Memoize a function.

    >>> @memoize
    ... def example(a, b):
    ...     return a + b

    This decorator adds memoization to simple functions.  The *first* call to
    a decorated function with a set of arguments will generate and cache a
    result.  Future calls with the same set of arguments will simply return the
    cached result.

    Caveats:

    - Only supports positional arguments
    - All arguments must be hashable
    - The cache is *not* thread-safe
    - The cache has no size limit

    :type callobj: callable

    :rtype: callable
    """
    cache = {}

    @wraps(callobj)
    def wrapper(*rest):
        if rest not in cache:
            cache[rest] = callobj(*rest)
        return cache[rest]

    return wrapper


def deprecate(extra=''):
    """
    Mark a function as deprecated.

    >>> @deprecate("Will be removed")
    ... def example(a, b):
    ...     return a + b

    :param str extra: more details to include in the deprecation warning

    :returns callable: returns a decorator
    """
    def wrapper(func):
        @wraps(func)
        def newfunc(*args, **kwargs):
            msg = "{!r} is deprecated".format(func.__name__)
            if extra:
                msg += ' ({!s})'.format(extra)
            _warn(msg, DeprecationWarning, stacklevel=2)
            return func(*args, **kwargs)
        return newfunc
    return wrapper
