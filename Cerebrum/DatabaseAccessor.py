# -*- coding: utf-8 -*-
# Copyright 2002-2020 University of Oslo, Norway
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
import logging

import Cerebrum.database
import Cerebrum.database.errors

_db_api_names = (Cerebrum.database.API_TYPE_CTOR_NAMES +
                 Cerebrum.database.errors.API_EXCEPTION_NAMES)


logger = logging.getLogger(__name__)


class DatabaseAccessor(object):

    __slots__ = _db_api_names + ('_db', 'logger')

    def __init__(self, database):
        assert isinstance(database, Cerebrum.database.Database)
        self._db = database
        self.logger = logger.getChild('DatabaseAccessor')

        # Copy driver-specific type constructors and exceptions.
        # We need this since the standard only defines their
        # names, and don't define any driver-independent way
        # to retrieve them.
        for name in _db_api_names:
            setattr(self, name, getattr(database, name))

    def execute(self, operation, *params, **kws):
        return self._db.execute(operation, *params, **kws)

    def query(self, query, *params, **kws):
        return self._db.query(query, *params, **kws)

    def query_1(self, query, *params, **kws):
        return self._db.query_1(query, *params, **kws)

    def nextval(self, seq_name):
        return self._db.nextval(seq_name)

    def currval(self, seq_name):
        return self._db.currval(seq_name)

    def setval(self, seq_name, val):
        return self._db.setval(seq_name, val)

    def commit(self):
        return self._db.commit()
