# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

from GroBuilder import GroBuilder
from Builder import Attribute, Method

import Registry

registry = Registry.get_registry()

__all__ = ['Date']

class Date(GroBuilder):
    primary = []
    slots = []
    method_slots = [
        Method('get_year', int),
        Method('get_month', int),
        Method('get_day', int),
        Method('get_hour', int),
        Method('get_minute', int),
        Method('get_second', int),
        Method('strftime', str, args=[('formatstr', str)]),
    ]

    def create_primary_key(cls, value):
        return (value, )

    create_primary_key = classmethod(create_primary_key)

    def __init__(self, value):
        self._value = value
        GroBuilder.__init__(self, nocache=True)

    def get_year(self):
        return self._value.year

    def get_month(self):
        return self._value.month

    def get_day(self):
        return self._value.day

    def get_hour(self):
        return self._value.hour

    def get_minute(self):
        return self._value.minute

    def get_second(self):
        return self._value.second

    def strftime(self, formatstr):
        return self._value.strftime(formatstr)

registry.register_class(Date)

# arch-tag: b91bce22-4551-41a3-a2ea-b84cd02944f2
