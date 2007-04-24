# -*- coding: iso-8859-1 -*-

# Copyright 2004-2006 University of Oslo, Norway
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

from SpineLib.DatabaseClass import DatabaseTransactionClass
from SpineLib.Date import Date
from SpineLib import SpineExceptions
from Types import SourceSystem, ValueDomain

from SpineLib import Registry
registry = Registry.get_registry()

import cereconf

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

    def get_date_none(self):
        return Date(None)

    get_date_none.signature = Date

    def get_date_now(self):
        return Date(mx.DateTime.now())
    
    get_date_now.signature = Date

    def get_date(self, year, month, day):
        date = Date(mx.DateTime.Date(year, month, day))
        date.set_format("%Y-%m-%d")
        return date

    get_date.signature = Date
    get_date.signature_args = [int, int, int]

    def get_datetime(self, year, month, day, hour, minute, second):
        return Date(mx.DateTime.DateTime(year, month, day, hour, minute, second))

    get_datetime.signature = Date
    get_datetime.signature_args = [int, int, int, int, int, int]

    def strptime(self, datestr, formatstr):
        """Get date from a string.
        
        Returns a Date-object reflecting the parsed date and time.
        """
        try:
            return Date(mx.DateTime.strptime(datestr.strip(), formatstr))
        except mx.DateTime.Error:
            raise SpineExceptions.ValueError('"%s" does not match the format "%s"' % (datestr, formatstr))

    strptime.signature = Date
    strptime.signature_args = [str, str]
    strptime.signature_exceptions = [SpineExceptions.ValueError]

    # Extentions are registered on the class, but queried via
    # command objects.
    _extentions = []
    def register_extention(cls, name):
        """Interface for letting modules register extentions"""
        cls._extentions.append(name)
    register_extention = classmethod(register_extention)
    
    def has_extention(self, name):
        """Interface for quering extentions"""
        return name in self._extentions
    has_extention.signature = int
    has_extention.signature_args = [str]
    
    def get_extentions(self):
        """Interface for quering extentions"""
        return self._extentions
    get_extentions.signature = [str]

    def get_system_lookup_order(self):
        """Get system lookup order from config"""
        db=self.get_database()
        return [SourceSystem(db, name=str(getattr(db.const, i)))
                for i in cereconf.SYSTEM_LOOKUP_ORDER]
    get_system_lookup_order.signature = [SourceSystem]

    def get_namespace(self, s):
        """Return namespace valuedomain for a type (server side config)"""
        db=self.get_database()
        namespace=cereconf.ENTITY_TYPE_NAMESPACE[s]
        return ValueDomain(db, name=namespace)
    get_namespace.signature=ValueDomain
    get_namespace.signature_args=[str]


registry.register_class(Commands)

# arch-tag: 71417222-2307-47cd-b582-9f793a502e6a
