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

from Cerebrum.Utils import Factory
import Cerebrum.Database
Database = Factory.get('Database')

class SpineDatabase(Database):
    """
    Extends the Cerebrum database class with useful stuff
    for a spine transaction.
    """
    
    def __init__(self, entity_id=None):
        Database.__init__(self)

        # start changelog
        if entity_id is None:
            self.cl_init(change_program='Spine')
        else:
            self.cl_init(change_by=entity_id)

        # Make sure the transactions don't step to much at each others feet
        # XXX Postgres-specific?
        self.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')

        # Pull in constants for convenience
	self.const = Factory.get('Constants')(self)

# arch-tag: 3a36a882-0fd8-4a9c-9889-9540095f93e3
