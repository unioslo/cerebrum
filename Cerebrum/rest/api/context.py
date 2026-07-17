# -*- coding: utf-8 -*-
#
# Copyright 2016-2024 University of Oslo, Norway
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
""" Application context utils."""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from flask import g


class ContextValue(object):
    """
    Application context value.

    This is a a data descriptor that stores its value on `flask.g`.  This
    provides easy access to app-specific named values.

    >>> from flask import Flask
    >>> app = Flask('doctest')
    >>> class Example(object):
    ...     value = ContextValue("example_value")

    >>> Example.value
    ContextValue('example_value')

    >>> e = Example()
    >>> with app.app_context():
    ...     e.value = str("foo")
    ...     e.value
    'foo'

    >>> with app.app_context():
    ...     del e.value
    ...     e.value
    None
    """

    def __init__(self, name, default=None):
        self.name = name
        self.default = default

    @property
    def attr(self):
        """ attribute name in the `flask.g` context. """
        return "__{!s}_{!s}".format(
            self.__class__.__name__,
            self.name)

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        return getattr(g, self.attr, self.default)

    def __set__(self, obj, value):
        if obj is None:
            return
        setattr(g, self.attr, value)

    def __delete__(self, obj):
        if obj is None:
            return
        if hasattr(g, self.attr):
            delattr(g, self.attr)

    def __repr__(self):
        return "{!s}('{!s}')".format(
            self.__class__.__name__,
            self.name)

    @classmethod
    def clear_object(cls, obj):
        """ Clear all ContextValue descriptors in `obj`. """
        obj_type = type(obj)
        for attr in dir(obj_type):
            if isinstance(getattr(obj_type, attr), cls):
                # call ContextValue.__delete__
                delattr(obj, attr)
