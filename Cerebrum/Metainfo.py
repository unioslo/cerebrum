# -*- coding: iso-8859-1 -*-
# Copyright 2003 University of Oslo, Norway
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

"""Stores meta information about the database, such as the version
number of the installed database schema."""

import pickle

from Cerebrum.Database import Errors

SCHEMA_VERSION_KEY = 'cerebrum_database_schema_version'

class Metainfo(object):
    def __init__(self, database):
        self.db = database

    def get_metainfo(self, name):
        value = self.db.query_1("""
        SELECT value
        FROM [:table schema=cerebrum name=cerebrum_metainfo]
        WHERE name=:name""", {'name': name})
        return pickle.loads(value)

    def set_metainfo(self, name, value):
        value = pickle.dumps(value)
        try:
            self.get_metainfo(name)
            self.db.execute("""
            UPDATE [:table schema=cerebrum name=cerebrum_metainfo]
            SET value=:value
            WHERE name=:name""", {'name': name, 'value': value}) 
        except Errors.NotFoundError:
            self.db.execute("""
            INSERT INTO [:table schema=cerebrum name=cerebrum_metainfo]
              (name, value)
            VALUES (:name, :value)""", {'name': name, 'value': value}) 
