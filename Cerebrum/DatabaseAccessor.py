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

class DatabaseAccessor(object):

    __slots__ = Database.API_TYPE_CTOR_NAMES + \
                Database.API_EXCEPTION_NAMES + ('_db',)

    def __init__(self, database):
        assert isinstance(database, Database.Database)
        self._db = database
        # Copy driver-specific type constructors and exceptions.
        for ctor in Database.API_TYPE_CTOR_NAMES:
            setattr(self, ctor, getattr(database, ctor))
        for exc in Database.API_EXCEPTION_NAMES:
            setattr(self, exc, getattr(database, exc))

    def execute(self, operation, *parameters):
        return self._db.execute(operation, *parameters)

    def query(self, query, *params):
        return self._db.query(query, *params)

    def query_1(self, query, *params):
        return self._db.query_1(query, *params)

    def nextval(self, seq_name):
        return self._db.nextval(seq_name)

    def commit(self):
        return self._db.commit()
