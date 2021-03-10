# coding: utf-8
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
Helper utils for implementing :py:meth:`object.__repr__`

This module contains mixin classes with basic, configurable, and reusable
object representations.

.. warning::
    These ``__repr__()`` implementations have no recursion protection - make
    sure to only use them for classes that cannot contain circular references.
"""


class _Example(object):
    """ Example class for documentation, doctests. """

    def __init__(self, a=None, b=None):
        self.a = a
        self.b = b


class ReprFieldMixin(object):
    """ Object representation with selected attributes.

    Examples:

    - ``<Baz a='text' b=3 c=None>``
    - ``<foo.bar.Baz a='text' b=3 c=None>``
    - ``<foo.bar.Baz a='text' b=3 c=None at 0x7f3ff7256ea0>``

    .. py:attribute:: repr_id

        Controls inclusion of the object id (e.g. ``at 0x7f3ff7256ea0``).
        ``True`` by default, but subclasses can set this to ``False``:

            >>> class FieldsNoId(ReprFieldMixin):
            ...     repr_id = False

            >>> repr(FieldsNoId())
            '<Cerebrum.utils.reprutils.FieldsNoId>'

    .. py:attribute:: repr_module

        Controls if the class name is prefixed by the module name (e.g.
        ``Cerebrum.utils.reprutils`` for classes in this module).  ``True`` by
        default, but subclasses can set this to ``False``.

            >>> class FieldsNoModule(ReprFieldMixin):
            ...     repr_module = False

            >>> repr(FieldsNoModule())
            '<FieldsNoModule at 0x...>'

    .. py:attribute:: repr_fields

        Ordered tuple of attribute names to include in the object
        representation:

            >>> class FieldsFoo(_Example, ReprFieldMixin):
            ...     repr_id = False
            ...     repr_module = False
            ...     repr_fields = ('a', 'b')

            >>> repr(FieldsFoo(b=2))
            '<FieldsFoo a=None b=2>'
    """
    repr_id = True
    repr_module = True
    repr_fields = ()

    # PY3:
    # @reprlib.recursive_repr(fillvalue="...")
    def __repr__(self):
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
    """ Object representation with eval-like output.

    Examples:

    - ``Baz('text', 3, None)``
    - ``foo.bar.Baz('text', b=3, c=None)``

    .. py:attribute:: repr_module

        See :py:attr:`ReprFieldMixin.repr_module`.

    .. py:attribute:: repr_args

        An ordered tuple of attribute names to use in the object
        representation.

            >>> class EvalArgs(_Example, ReprEvalMixin):
            ...     repr_module = False
            ...     repr_args = ('a', 'b')
            >>> repr(EvalArgs(b=2))
            'EvalArgs(None, 2)'

    .. py:attribute:: repr_kwargs

        A tuple of attribute names to use as keyword args in the
        representation.

            >>> class EvalKeywords(_Example, ReprEvalMixin):
            ...     repr_module = False
            ...     repr_kwargs = ('a', 'b')
            >>> repr(EvalKeywords(b=2))
            'EvalKeywords(a=None, b=2)'

        All keyword args are sorted alphabetically, and appears after any
        :py:attr:`repr_args` and :py:attr:`repr_args_attr`

    .. py:attribute:: repr_args_attr

        Name of an attribute that contains a sequence of variable length
        argument values.

            >>> class EvalVarArgs(ReprEvalMixin):
            ...    repr_module = False
            ...    repr_args = ('foo',)
            ...    repr_args_attr = 'args'
            ...    def __init__(self, foo, *args):
            ...         self.foo = foo
            ...         self.args = args
            >>> repr(EvalVarArgs(1, 2, 3))
            'EvalVarArgs(1, 2, 3)'

        Any values in this attribute are included *after* :py:attr:`repr_args`,
        but before any :py:attr:`repr_kwargs`

    .. py:attribute:: repr_kwargs_attr

        Name of an attribute that contains a dict of variable length keyword
        arguments — similar to :py:attr:`.repr_args_attr`, but for
        ``**kwargs``.
    """
    repr_module = True
    repr_args = ()
    repr_args_attr = None
    repr_kwargs = ()
    repr_kwargs_attr = None

    # PY3:
    # @reprlib.recursive_repr(fillvalue="...")
    def __repr__(self):
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


if __name__ == "__main__":
    # name hack required for the `repr_module=True` cases
    __name__ = 'Cerebrum.utils.reprutils'
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
