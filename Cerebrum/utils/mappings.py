# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
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
This module contains common implementations of the collections.mapping API.
"""

import warnings
try:
    # PY3: collections.Mapping disappears in 3.8
    from collections.abc import Mapping as _Mapping
except ImportError:
    from collections import Mapping as _Mapping

import six


class SimpleMap(_Mapping):
    """
    A simple mapping base class.

    This is a default implementation of ``collections[.abc].Mapping``, for
    use with specialized dict-like objects.  These are typically mappings that
    needs to be *immutable* (but init-able) or have special methods for
    implementing mutability (e.g. register decorators for functions, validation
    of values, etc...).
    """

    def __init__(self, *args, **kwargs):
        self._data = {}
        for k, v in dict(*args, **kwargs).items():
            self.set(k, v)

    def transform_key(self, key):
        """
        Transform a key.

        This method can be overloaded to normalize and/or validate keys.  This
        can be used e.g. to provide forced lowercase string keys and
        case-insensitive lookups.
        """
        return key

    def transform_value(self, value):
        """
        Transform a value.

        This method can be overloaded to normalize and/or validate keys.
        """
        return value

    def set(self, key, value):
        # We don't add a __setitem__ as this is not really intended to be a
        # MutableMapping.
        nkey = self.transform_key(key)
        nvalue = self.transform_value(value)
        self._data[nkey] = nvalue

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    def __getitem__(self, key):
        nkey = self.transform_key(key)
        return self._data[nkey]

    def __repr__(self):
        return '<{cls.__name__} at 0x{id:02x}>'.format(
            cls=type(self),
            id=id(self),
        )

    def viewkeys(self):
        # Only provided for PY2-compatibility with six.viewkeys()
        if six.PY3:
            warnings.warn('viewkeys() is deprecated, use keys()',
                          DeprecationWarning, stacklevel=2)
        return six.viewkeys(self._data)

    def viewvalues(self):
        # Only provided for PY2-compatibility with six.viewvalues()
        if six.PY3:
            warnings.warn('viewvalues() is deprecated, use values()',
                          DeprecationWarning, stacklevel=2)
        return six.viewvalues(self._data)

    def viewitems(self):
        # Only provided for PY2-compatibility with six.viewitems()
        if six.PY3:
            warnings.warn('viewitems() is deprecated, use items()',
                          DeprecationWarning, stacklevel=2)
        return six.viewitems(self._data)


class DecoratorMap(SimpleMap):
    """
    A mapping/mixin that adds a class/function register decorator.

    >>> filters = CallbackDict()
    >>> @filters.register('pascal')
    ... def upper_camel_case(s):
    ...     return ''.join(
    ...         w[0].upper() + w[1:].lower()
    ...         for w in (item.strip() for item in s.split() if item.strip()))
    >>> filters['pascal']('foo  BAR  bAz')
    'FooBarBaz'

    Decorated values are stored under the given key and returned as-is:

    >>> filters.register('lower')(str.lower) is str.lower
    True
    """

    def register(self, item):
        def wrapper(fn):
            self.set(item, fn)
            return fn
        return wrapper
