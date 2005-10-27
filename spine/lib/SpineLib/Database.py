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

from threading import RLock
from Cerebrum.Utils import Factory
import Cerebrum.Errors
import Cerebrum.Database
import SpineExceptions
Database = Factory.get('Database')

class SpineDatabase(Database):
    """This class extends the commit() method of the Cerebrum database
    to include locking. Using this scheme, only one transaction can
    commit at a time.
    """
    
    def __init__(self, entity_id=None):
        self._lock = RLock()
        Database.__init__(self)
        if entity_id is None:
            self.cl_init(change_program='Spine')
        else:
            self.cl_init(change_by=entity_id)

        # i hope this is the correct way to do it
        self.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')

    def lock(self):
        self._lock.acquire()

    def release(self):
        self.rollback_log() # just in case
        self.rollback() # will this break the database?
        self._lock.release()

    def query(self, sql, keys={}):
        """Wraps around the query call on the database to catch exceptions
        and rethrow proper Spine exceptions."""
        try:
            return super(SpineDatabase, self).query(sql, keys)
        except Cerebrum.Errors.DatabaseConnectionError, e:
            SpineExceptions.DatabaseError('Connection to the database failed', str(e), sql)
        except Cerebrum.Errors.DatabaseException, e:
            SpineExceptions.DatabaseError('Error during query', str(e), sql)
        except Cerebrum.Database.DatabaseError, e:
            SpineExceptions.DatabaseError('Error during query', str(e), sql)

    def execute(self, sql, keys={}):
        """Wraps around the execute call on the database to catch exceptions
        and rethrow proper Spine exceptions."""
        try:
            return super(SpineDatabase, self).execute(sql, keys)
        except Cerebrum.Errors.DatabaseConnectionError, e:
            SpineExceptions.DatabaseError('Connection to the database failed', str(e), sql)
        except Cerebrum.Errors.DatabaseException, e:
            SpineExceptions.DatabaseError('Error during query', str(e), sql)
        except Cerebrum.Database.DatabaseError, e:
            SpineExceptions.DatabaseError('Error during query', str(e), sql)
    
    def query_1(self, sql, keys={}):
        """Wraps around the query_1 call on the database to catch exceptions
        and rethrow proper Spine exceptions."""
        try:
            return super(SpineDatabase, self).query_1(sql, keys)
        except Cerebrum.Errors.NotFoundError, e:
            raise SpineExceptions.NotFoundError(*e.args)
        except Cerebrum.Errors.TooManyRowsError, e:
            raise SpineExceptions.TooManyMatchesError(*e.args)
        except Cerebrum.Errors.DatabaseConnectionError, e:
            raise SpineExceptions.DatabaseError('Connection to the database failed', str(e), sql)
        except Cerebrum.Errors.DatabaseException, e:
            raise SpineExceptions.DatabaseError('Error during query', str(e), sql)
        except Cerebrum.Database.DatabaseError, e:
            raise SpineExceptions.DatabaseError('Error during query', str(e), sql)


# arch-tag: 3a36a882-0fd8-4a9c-9889-9540095f93e3
