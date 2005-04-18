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

from SpineLib.SpineClass import SpineClass
from SpineLib.Builder import Attribute, Method
from SpineLib import Registry

from Commands import Commands

registry = Registry.get_registry()

__all__ = ['Date']

class Date(SpineClass):
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
        Method('strftime', str, args=[('formatstr', str)]),
        Method('toString', str)
    ]

    def create_primary_key(cls, value):
        return (value, )

    create_primary_key = classmethod(create_primary_key)

    def __init__(self, value, *args, **vargs):
        self._value = value
        SpineClass.__init__(self, *args, **vargs)

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

    def toString(self):
        format = getattr(self, self.get_attr('format').get_name_private(), None)
        if format is None:
            return str(self._value)
        else:
            return self.strftime(format)

registry.register_class(Date)

# Commands for clients to create Date-objects.

def get_date_now(self):
    return Date(mx.DateTime.now())

def get_date(self, year, month, day):
    date = Date(mx.DateTime.Date(year, month, day))
    date.set_format("%Y-%m-%d")
    return date

def get_datetime(self, year, month, day, hour, minute, second):
    return Date(mx.DateTime.DateTime(year, month, day, hour, minute, second))

def strptime(self, datestr, formatstr):
    """Get date from a string.
    
    Returns a Date-object reflecting the parsed date and time.
    """
    return Date(mx.DateTime.strptime(datestr, formatstr))

def get_date_none(self):
        return Date(None)

Commands.register_method(Method('get_date_none', Date), get_date_none)

# Registers the commands in the Commands-class

Commands.register_method(Method('get_date_now', Date), get_date_now)

date_args = [('year', int), ('month', int), ('day', int)]
Commands.register_method(Method('get_date', Date, args=date_args), get_date)

datetime_args = [('year', int), ('month', int), ('day', int),
                 ('hour', int), ('minute', int), ('second', int)]
Commands.register_method(Method('get_datetime', Date, args=datetime_args), get_datetime)

strptime_args = [("datestr", str), ("formatstr", str)]
Commands.register_method(Method('strptime', Date, args=strptime_args), strptime)

# arch-tag: 57d51c14-a6c9-4913-a011-1f7222ad79b5
