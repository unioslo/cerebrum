# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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

import mx.DateTime

from Builder import Builder, Attribute, Method
import SpineExceptions

import Registry
registry = Registry.get_registry()

__all__ = ['Date']

class Date(Builder):
    primary = []
    slots = [
        Attribute('format', str, write=True)
    ]
    method_slots = [
        Method('get_year', int),
        Method('get_month', int),
        Method('get_day', int),
        Method('get_hour', int),
        Method('get_minute', int),
        Method('get_second', int),
        Method('get_unix', int),
        Method('strftime', str, args=[('formatstr', str)]),
        Method('to_string', str)
    ]

    def __init__(self, value, *args, **vargs):
        super(Date, self).__init__(*args, **vargs)
        self._value = value

    def get_primary_key(self):
        return (self._value, )

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

    def get_unix(self):
        return int(self._value.ticks())

    def strftime(self, formatstr):
        return self._value.strftime(formatstr)

    def to_string(self):
        format = getattr(self, self.get_attr('format').get_name_private(), None)
        if format is None:
            return str(self._value)
        else:
            return self.strftime(format)

registry.register_class(Date)

# arch-tag: 57d51c14-a6c9-4913-a011-1f7222ad79b5
