# -*- coding: utf-8 -*-
# Copyright 2018-2020 University of Oslo, Norway
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
Parameter conversions for paramstyle.

String interpolation in Cerebrum expects a named parameter style and dict
parameters. This module contains adapters to translate these parameters to
different parameter styles.


Example
-------
>>> convert = Numbered()
>>> convert.register('foo')  # first registered name
':1'
>>> convert.register('bar')  # another name
':2'
>>> convert.register('foo')  # name already seen
':1'
>>> convert({'foo': 'x', 'bar': 2})  # extracts parameters from dict
('x', 2)


Usage
-----
The converters would typically be combined with a lexer in order to translate
placeholders from a full sql statement:

::

    param_style = Numbered

    def _fix(statement, params):
        # require dict-like params
        params = params or {}
        assert isinstance(params, dict)

        # make a param style converter for this statement
        param_convert = param_style()

        # identify placeholders and replace with converted placeholder
        fixed = ''
        for token, text in lex(statement):
            if token == 'placeholder':
                name = text[1:]  # assumes placeholders on format ':name'
                fixed += param_convert.register(name)
            else:
                fixed += text

        # return fixed statement and converted params
        return fixed, param_convert(params)

See https://www.python.org/dev/peps/pep-0249/#paramstyle
"""


_PARAMSTYLES = {}


def register_converter(style):
    def wrapper(cls):
        _PARAMSTYLES[style] = cls
        return cls
    return wrapper


def get_converter(style):
    if style not in _PARAMSTYLES:
        raise NotImplementedError(
            "No converter for param_style {0}".format(style))
    return _PARAMSTYLES[style]


class Base(object):
    """Convert bind parameters to appropriate paramstyle."""

    __slots__ = ('names',)

    def __init__(self):
        self.names = []

    def __contains__(self, name):
        return name in self.names

    def _verify_params(self, params):
        """Verify that all registered names are present in `params`."""
        missing = set(name for name in self.names if name not in params)
        if missing:
            raise ValueError('Missing params: %s' %
                             ' '.join(repr(n) for n in sorted(missing)))

    def __call__(self, param_dict):
        """Convert parameters to the appropriate format."""
        raise NotImplementedError()

    def register(self, name):
        """
        Registers a bind parameter.

        :param name: the input parameter name

        :return: returns a formatted placeholder with this param style.
        """
        raise NotImplementedError()


class _Ordered(Base):
    """Abstract converter for formats that use ordered tuples."""

    __slots__ = ()
    param_str = None

    def __call__(self, param_dict):
        self._verify_params(param_dict)
        return tuple(param_dict[name] for name in self.names)

    def register(self, name):
        self.names.append(name)
        return self.param_str


@register_converter('qmark')
class Qmark(_Ordered):
    """
    Param format '?'

    Example:
        "foo = :x and bar = :x and baz = :y", {'x': 1, 'y': 2}

    Becomes:
        "foo = ? and bar = ? and baz = ?, (1, 1, 2)
    """

    __slots__ = ()
    param_str = '?'


@register_converter('format')
class Format(_Ordered):
    """
    Param format '%s'.

    Example:
        "foo = :x and bar = :x and baz = :y", {'x': 1, 'y': 2}

    Becomes:
        "foo = %s and bar = %s and baz = %s, (1, 1, 2)
    """

    __slots__ = ()
    param_str = '%s'


@register_converter('numeric')
class Numeric(Base):
    """
    Param format ':n'.

    Example:
        "foo = :x and bar = :x and baz = :y", {'x': 1, 'y': 2}

    Becomes:
        "foo = :1 and bar = :1 and baz = :2, (1, 2)
    """

    __slots__ = ()

    def __call__(self, param_dict):
        self._verify_params(param_dict)
        return tuple(param_dict[name] for name in self.names)

    def register(self, name):
        if name not in self.names:
            self.names.append(name)
        # Construct return value on our own, as it must include a
        # numeric index associated with `name` and not `name` itself.
        return ':' + str(self.names.index(name) + 1)


class _NamedParams(Base):
    """Abstract converter for formats that fetches names from a dict."""

    __slots__ = ()
    param_format = None

    def __call__(self, param_dict):
        self._verify_params(param_dict)
        return param_dict

    def register(self, name):
        self.names.append(name)
        return self.param_format % {'name': name}


@register_converter('named')
class Named(_NamedParams):
    """
    Param format ':name'.

    Example:
        "foo = :x and bar = :x and baz = :y", {'x': 1, 'y': 2}

    Becomes:
        "foo = :x and bar = :x and baz = :y", {'x': 1, 'y': 2}
    """

    __slots__ = ()
    param_format = ':%(name)s'


@register_converter('pyformat')
class Pyformat(_NamedParams):
    """
    Param format '%(name)s'.

    Example:
        "foo = :x and bar = :x and baz = :y", {'x': 1, 'y': 2}

    Becomes:
        "foo = %(x)s and bar = %(x)s and baz = %(y)s", {'x': 1, 'y': 2}
    """

    __slots__ = ()
    param_format = '%%(%(name)s)s'
