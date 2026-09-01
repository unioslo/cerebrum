# encoding: utf-8
#
# Copyright 2016-2026 University of Oslo, Norway
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
Simple, reusable data descriptors.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from . import reprutils


class Descriptor(reprutils.ReprFieldMixin):
    """
    Basic data descriptor for storing values in the owner object dict.

    This descriptor doesn't really provide any direct features, as it is
    intended mainly as a base class for other descriptors.  It works much like
    a regular attribute, but:

    1. Provides a unique, mangled attribute name to use in the owner class
    2. Adds a simple, but useful descriptor repr
    """
    repr_id = True
    repr_module = True
    repr_fields = ("name",)

    descriptor_delete_strict = True
    """
    Delete rule for this descriptor.

    If this is True (default), then it is an error to ``del`` the descriptor
    value if it hasn't been assigned a value first.  Subclasses can override
    this setting.
    """

    def __init__(self, name):
        self.name = name

    def get_default(self, obj):
        """
        Abstract method - get a default value for this descriptor.

        This can be overridden by subclasses to provide a default value.
        """
        raise AttributeError(self.name)

    def transform_value(self, value):
        """
        Abstract method - normalize and validate a new value.

        This can be overridden by subclasses to provide validation and/or
        normalization.
        """
        return value

    @property
    def attr_name(self):
        """ Owner object attribute name. """
        # Mangle the attribute name, so that the actual attribute is uniquely
        # named in the owner object dict.
        #
        # >>> repr(Foo.example)
        # <Cerebrum.utils.descriptors.Descriptor... at 0x7fca531f7bd0>
        # >>> f = Foo(example=1024)
        # >>> repr(f.__dict__)
        # {'_Descriptor__example_7fca531f7bd0': 1024}
        return '_{!s}__{!s}_{:x}'.format(
            self.__class__.__name__,
            self.name,
            id(self),
        )

    def __get__(self, obj, cls):
        if obj is None:
            return self
        try:
            return getattr(obj, self.attr_name)
        except AttributeError:
            return self.get_default(obj)

    def __set__(self, obj, value):
        if obj is None:
            return
        value = self.transform_value(value)
        setattr(obj, self.attr_name, value)

    def __delete__(self, obj):
        if obj is None:
            return
        try:
            delattr(obj, self.attr_name)
        except AttributeError:
            if self.descriptor_delete_strict:
                raise AttributeError(self.name)


class DefaultDescriptor(Descriptor):
    """
    A simple data descriptor with a default value.

    This descriptor has a default value, which is returned if no explicit
    value has been set:

    >>> class Foo(object):
    ...     bar = DefaultDescriptor("bar", "default value")
    >>> f = Foo()
    >>> f.bar
    "default value"

    The descriptor can still be assigned other values

    >>> f.bar = "custom value"
    >>> f.bar
    "custom value"

    Deleting the descriptor value will reset it back to the default:

    >>> del f.bar
    >>> f.bar
    "default value"

    """

    # It is not an attribute error to `del` this attribute when it isn't set
    descriptor_delete_strict = False

    def __init__(self, name, default=None):
        self.name = name
        self.default = default

    def get_default(self, obj):
        return self.default


class lazy_property(Descriptor):  # noqa: N801
    """
    A lazy initialization data descriptor.

    Wrap a function with this class to make it a property-like data descriptor,
    with the wrapped function as factory.

    Like :func:`builtins.property`, the wrapped function is called when we look
    up the descriptor value:

    >>> class Foo(object):
    ...     @lazy_property
    ...     def example(self):
    ...         return 2**10
    >>> f = Foo()
    >>> f.example
    1024

    However, this only happens when no value has been set or cached.  We can
    override the value by setting it explicitly:

    >>> f.example = 2**8
    >>> f.example
    256

    Deleting the descriptor value will reset it and cause the wrapped factory
    function to be called again on the next lookup:

    >>> del f.example
    >>> f.example
    1024
    """

    # It is not an attribute error to `del` this attribute when it isn't set
    descriptor_delete_strict = False

    def __init__(self, func):
        """ Build a data descriptor.

        :param callable func:
            The initializer function.
        """
        self.__doc__ = func.__doc__
        self._func = func

    @property
    def name(self):
        # Use the wrapped function name as name
        return self._func.__name__

    def get_default(self, obj):
        return self._func(obj)

    def __get__(self, obj, cls):
        if obj is None:
            return self
        try:
            return getattr(obj, self.attr_name)
        except AttributeError:
            value = self.get_default(obj)
            setattr(obj, self.attr_name, value)
            return value
