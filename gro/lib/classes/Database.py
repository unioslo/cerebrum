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

from threading import Lock
from Cerebrum.Utils import Factory
Database = Factory.get('Database')
from Cerebrum.gro.Cerebrum_core import Errors

__all__ = ['get_database']

class GroDatabase(Database):
    """This class extends the commit() method of the Cerebrum database
    to include locking. Using this scheme, only one transaction can
    commit at a time.
    """
    def __init__(self):
        self.lock = Lock()
        Database.__init__(self)
        Database.cl_init(self, change_program='GRO')
    def commit(self):
        self.lock.acquire()
        try:
            Database.commit(self)
        except Exception, e:
            self.lock.release()
            raise Errors.TransactionError('Failed to commit: %s' % e)
        self.lock.release()

db = None

def get_database():
    global db
    if db is None:
        db = GroDatabase()
    return db
