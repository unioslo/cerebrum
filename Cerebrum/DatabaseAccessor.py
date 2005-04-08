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

"""Provide objects with database access methods."""

from Cerebrum import Database
from Cerebrum.Utils import Factory

class DatabaseAccessor(object):

    __slots__ = Database.API_TYPE_CTOR_NAMES + \
                Database.API_EXCEPTION_NAMES + ('_db', '__logger')

    def __init__(self, database):
        assert isinstance(database, Database.Database)
        self._db = database
        self.__logger = None
        # Copy driver-specific type constructors and exceptions.
        # We need this since the standard only defines their
        # names, and don't define any driver-independent way 
        # to retrieve them. 
        # These are type constructors as defined in DB-API 2.0
        for ctor in Database.API_TYPE_CTOR_NAMES:
            setattr(self, ctor, getattr(database, ctor))
        # These are exception constructors as defined in DB-API 2.0
        for exc in Database.API_EXCEPTION_NAMES:
            setattr(self, exc, getattr(database, exc))

    def execute(self, operation, *params, **kws):
        return self._db.execute(operation, *params, **kws)

    def query(self, query, *params, **kws):
        return self._db.query(query, *params, **kws)

    def query_1(self, query, *params, **kws):
        return self._db.query_1(query, *params, **kws)

    def nextval(self, seq_name):
        return self._db.nextval(seq_name)

    def commit(self):
        return self._db.commit()

    def _get_logger(self):
        if self.__logger is None:
            self.__logger = Factory.get_logger()
        return self.__logger
    logger = property(_get_logger, None, None,
                      "Cerebrum logger object for use from library methods.")

# arch-tag: 00d1fe61-c527-4159-9f4f-74510846d83d
