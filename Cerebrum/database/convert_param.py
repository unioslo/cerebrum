# -*- coding: utf-8 -*-
# Copyright 2018 University of Oslo, Norway
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
""" Parameter conversions for paramstyle.

See https://www.python.org/dev/peps/pep-0249/#paramstyle
"""


PARAMSTYLES = {}


def register_converter(style):
    def wrapper(cls):
        PARAMSTYLES[style] = cls
        return cls
    return wrapper


def get_converter(style):
    if style not in PARAMSTYLES:
        raise NotImplementedError(
            "No converter for param_style {0}".format(style))
    return PARAMSTYLES[style]


class Base(object):

    """Convert bind parameters to appropriate paramstyle."""

    __slots__ = ('map',)
    # To be overridden in subclasses.
    param_format = None

    def __init__(self):
        self.map = []

    def __call__(self, param_dict):
        #
        # DCOracle2 does not treat bind parameters passed as a list
        # the same way it treats params passed as a tuple.  The DB API
        # states that "Parameters may be provided as sequence or
        # mapping", so this can be construed as a bug in DCOracle2.
        return tuple([param_dict[i] for i in self.map])

    def register(self, name):
        return self.param_format % {'name': name}


@register_converter('nonrepeat')
class Nonrepeat(Base):
    __slots__ = ()

    def register(self, name):
        self.map.append(name)
        return super(Nonrepeat, self).register(name)


@register_converter('qmark')
class Qmark(Nonrepeat):
    __slots__ = ()
    param_format = '?'


@register_converter('format')
class Format(Nonrepeat):
    __slots__ = ()
    param_format = '%%s'


@register_converter('numeric')
class Numeric(Base):
    __slots__ = ()

    def register(self, name):
        if name not in self.map:
            self.map.append(name)
        # Construct return value on our own, as it must include a
        # numeric index associated with `name` and not `name` itself.
        return ':' + str(self.map.index(name) + 1)


@register_converter('to_dict')
class To_dict(Base):
    __slots__ = ()

    def __init__(self):
        # Override to avoid creating self.map; that's not needed here.
        pass

    def __call__(self, param_dict):
        # Simply return `param_dict` as is.
        return param_dict


@register_converter('named')
class Named(To_dict):
    __slots__ = ()
    param_format = ':%(name)s'


@register_converter('pyformat')
class Pyformat(To_dict):
    __slots__ = ()
    param_format = '%%(%(name)s)s'
