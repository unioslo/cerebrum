# encoding: utf-8
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
""" This module contains simple reuseable data descriptors. """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)


class lazy_property(object):  # noqa: N801
    """ A lazy initialization data descriptor.

    Wrap a function with this class to make it a data descriptor/property, with
    the wrapped function as factory.

    Example:

    >>> class Foo(object):
    ...     @lazy_property
    ...     def example(self):
    ...         return 2**10
    >>> f = Foo()
    >>> f.example
    1024
    >>> f.example = 2**8
    >>> f.example
    256
    >>> del f.example
    >>> f.example
    1024

    """

    def __init__(self, func):
        """ Build a data descriptor.

        :param callable func:
            The initializer function.
        """
        self.__doc__ = func.__doc__
        self._func = func

    @property
    def attr_name(self):
        """ The attribute name where the actual value is stored. """
        # Mangle the attribute name, so that the actual attribute is uniquely
        # named in the object dict.
        #
        # >>> repr(Foo.example)
        # <Cerebrum.utils.funcwrap.lazy_property object at 0x7fca531f7bd0>
        # >>> repr(f.dict)
        # {'__lazy_property_example_7fca531f7bd0': 1024}
        return '__{!s}_{!s}_{:x}'.format(
            self.__class__.__name__,
            self._func.__name__,
            id(self))

    def __get__(self, obj, cls):
        """ Fetch (and if neccessary, initialize) the property value. """
        if obj is None:
            return self
        try:
            return getattr(obj, self.attr_name)
        except AttributeError:
            setattr(obj, self.attr_name, self._func(obj))
            return getattr(obj, self.attr_name)

    def __set__(self, obj, value):
        """ Set a custom property value.

        This will replace the property value, whether the value has been
        initialized or not.
        """
        setattr(obj, self.attr_name, value)

    def __delete__(self, obj):
        """ Delete the (potentially) initialized value.

        This will cause the property to run the initialization function the
        next time it is accessed.
        """
        if obj is None:
            return
        try:
            delattr(obj, self.attr_name)
        except AttributeError:
            pass
