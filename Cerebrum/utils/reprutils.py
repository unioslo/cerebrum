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
Helper utils for implementing object representation.

This module contains mixin classes with reusable :meth:`object.__repr__`
implementations.  The repr format can be configured in subclasses by overriding
default class attributes.

.. warning::
   These mixins do not provide recursion protection - make sure to only use
   them for classes that cannot contain circular references.

   This can be solved using :func:`reprlib.recursive_repr` on Python 3

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
)


class ReprFieldMixin(object):
    """
    Object representation with selected values.

    This mixin provides an object representation with optional key=value
    fields.  The format can be changed by class attributes in subclasses:

      - ``<foo.bar.Baz at 0x7f3ff7256ea0>`` (default)
      - ``<Baz at 0x7f3ff7256ea0>``
      - ``<foo.bar.Baz>``
      - ``<Baz a='text' b=3 c=None>``

    """

    repr_id = True
    """
    Include object id (e.g. ``<Baz at 0x7f3ff7256ea0>``) in repr.

    The default (``True``) will include e.g. ``at 0x7f3ff7256ea0`` to
    the repr, but subclasses can set this to ``False`` for a more compact
    representation.
    """

    repr_module = True
    """
    Use fully qualified class name (e.g. ``<foo.bar.Baz>``) in repr.

    The default (``True``) will use both the module name and class name.
    Subclasses can set this to ``False`` for more compact representation.
    """

    repr_fields = ()
    """
    Add attributes (e.g. ``<Baz a='text' b=3 c=None>``) to repr.

    This is an ordered tuple of attribute or property names to
    include.  Attribute names that are missing will be omitted.
    """

    # PY3:
    # @reprlib.recursive_repr(fillvalue="...")
    def __repr__(self):
        """
        Get a string representation.

        This common implementation allows the format to be changed using
        class attributes ``repr_id``, ``repr_module`` and ``repr_fields``.
        """
        cls = type(self)

        if cls.repr_module and cls.__module__:
            name = cls.__module__ + '.' + cls.__name__
        else:
            name = cls.__name__

        # select field and value pairs
        pairs = tuple(
            (k, getattr(self, k))
            for k in cls.repr_fields
            if hasattr(self, k))

        # format field and value pairs
        pretty = ' '.join(
            str(attr) + '=' + repr(value)
            for attr, value in pairs
        )

        if cls.repr_id:
            obj_id = '0x{:02x}'.format(id(self))
        else:
            obj_id = ''

        return '<{name}{fields}{obj_id}>'.format(
            name=name,
            fields=(' ' + pretty if pretty else ''),
            obj_id=(' at ' + obj_id if obj_id else ''),
        )


class ReprEvalMixin(object):
    """
    Object representation with eval-like output.

    This mixin provides an object representation similar to most built-ins,
    e.g.: ``Baz('text', b=3, c=None)``, and can be used to create an eval-able
    string from objects.

    Init-arguments are re-constructed according to the
    ``repr_args``/``repr_args_attr`` and ``repr_kwargs``/``repr_kwargs_attr``
    class attributes:
    ::

        class Baz(ReprEvalMixin):
            repr_args = ('a',)
            repr_kwargs_attr = '_kwargs'

            def __init__(self, a, **kwargs):
                self.a = a
                self._kwargs = kwargs
    """

    repr_module = True
    """
    Use fully qualified class name (e.g. ``foo.bar.Baz()``) in repr.

    The default (``True``) will use both the module name and class name.
    Subclasses can set this to ``False`` for more compact representation.
    """

    repr_args = ()
    """
    Get positional args from attributes.

    The value is an ordered tuple of attribute names to include.
    """

    repr_args_attr = None
    """
    Get positional args from a list.

    Use this to look up a sequence of positional arguments from an object
    attribute.  This can be used to re-construct a variable argument list
    (``*args``).

    Values in this attribute are added *after* ``repr_args``, but before any
    ``repr_kwargs``.
    """

    repr_kwargs = ()
    """
    Get keyword args from attributes.

    The value is a tuple of attribute names to include as keyword args.

    All keyword args are sorted alphabetically, and appear after positional
    arguments.
    """

    repr_kwargs_attr = None
    """
    Get keyword args from a dict.

    Use this to look up a mapping of argument names and values from an object
    attribute.  Similar to ``repr_args_attr``, but for ``**kwargs``.
    """

    # PY3:
    # @reprlib.recursive_repr(fillvalue="...")
    def __repr__(self):
        """
        Get a string representation.

        This common implementation allows the format to be changed using
        class attributes ``repr_module``, ``repr_args``, ``repr_args_attr``,
        ``repr_kwargs``, and ``repr_kwargs_attr``.
        """
        cls = type(self)

        if cls.repr_module and cls.__module__:
            name = cls.__module__ + '.' + cls.__name__
        else:
            name = cls.__name__

        # select args
        args = tuple(
            getattr(self, attr)
            for attr in cls.repr_args
            if hasattr(self, attr))

        # select kwargs
        kwargs = {
            k: getattr(self, k)
            for k in cls.repr_kwargs
            if hasattr(self, k)}

        # select variable *args, **kwargs
        if cls.repr_args_attr:
            args = args + tuple(getattr(self, cls.repr_args_attr, ()))
        if cls.repr_kwargs_attr:
            kwargs.update(getattr(self, cls.repr_kwargs_attr, {}))

        pretty_args = (
            # format args
            tuple(repr(a) for a in args)
            # format kwargs
            + tuple(str(k) + '=' + repr(kwargs[k])
                    for k in sorted(kwargs))
        )

        return '{name}({args})'.format(
            name=name,
            args=', '.join(pretty_args),
        )
