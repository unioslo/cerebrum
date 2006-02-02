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

from SpineLib.Builder import Method
from SpineLib.DatabaseClass import DatabaseTransactionClass
from SpineLib.Date import Date
from SpineLib import SpineExceptions

from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['Commands']

class Commands(DatabaseTransactionClass):
    """Collection of 'static' methods.

    This is the main class for 'static' methods in the cerebrum core
    like create_<core-class>. Since we dont support static methods on
    objects servered over corba, we create command-classes which
    contains those 'static' methods.

    This class should not implement methods specific to other classes,
    instead use Registry.get_registry().register_method().
    """

    method_slots = (
        Method('get_date_now', Date),
        Method('get_date', Date, args=[('year', int), ('month', int), ('day', int)]),
        Method('get_datetime', Date, args=[('year', int), ('month', int), ('day', int), ('hour', int), ('minute', int), ('second', int)]),
        Method('strptime', Date, args=[('datestr', str), ('formatstr', str)], exceptions=[SpineExceptions.ValueError]),
        Method('get_date_none', Date)
    )

    def get_date_none(self):
        return Date(None)

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
        try:
            return Date(mx.DateTime.strptime(datestr.strip(), formatstr))
        except mx.DateTime.Error:
            raise SpineExceptions.ValueError('"%s" does not match the format "%s"' % (datestr, formatstr))

registry.register_class(Commands)

# arch-tag: 71417222-2307-47cd-b582-9f793a502e6a
