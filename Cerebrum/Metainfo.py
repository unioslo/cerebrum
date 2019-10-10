# -*- coding: utf-8 -*-
# Copyright 2003-2018 University of Oslo, Norway
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

from Cerebrum import Errors

SCHEMA_VERSION_KEY = 'cerebrum_database_schema_version'


class Metainfo(object):

    def __init__(self, database):
        self.db = database

    def get_metainfo(self, name):
        """List version number of module name

        :type name: basestring
        :param name: Module name e.g sqlmodule_bofhd_auth

        :rtype: basestring or tuple
        :return: version number
        """
        value = self.db.query_1("""
        SELECT value
        FROM [:table schema=cerebrum name=cerebrum_metainfo]
        WHERE name=:name""", {'name': name})
        # If it is not saved in the old format pickle.loads() should fail and
        # we simply return the string as it is instead.
        try:
            return_value = pickle.loads(str(value))
        except Exception:
            return_value = str(value)
        return return_value

    def list(self):
        """List the modules with version numbers in cerebrum_metainfo

        :rtype: list
        :return: modules on form [('module name', 'version number'), (), ... ]
        """
        modules = self.db.query("""
        SELECT name, value
        FROM [:table schema=cerebrum name=cerebrum_metainfo]""")
        # Try doing the old method first. If that fails we assume that the
        # switch from pickle serialized values to regular strings has happened.
        try:
            return_list = [(row['name'], pickle.loads(str(row['value']))) for
                           row in modules]
        except Exception:
            return_list = [(row['name'], row['value']) for row in modules]
        return return_list

    def set_metainfo(self, name, value):
        """Set the version number of a module in the cerebrum_metainfo table

        :type name: basestring
        :param name: Modulename e.g 'sqlmodule_bofhd_auth'

        :type value: basestring
        :param value: version number e.g '0.9.20'
        """
        if isinstance(value, tuple):
            value = '.'.join(map(str, value))
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

    def del_metainfo(self, name):
        """Delete entry from metainfo table

        :type name: basestring
        :param name: Modulename e.g 'sqlmodule_bofhd_auth'
        """
        try:
            self.get_metainfo(name)
        except Errors.NotFoundError:
            # Nothing to delete, ignore
            pass
        else:
            binds = {'name': name}
            self.db.execute(
                """
                DELETE FROM [:table schema=cerebrum name=cerebrum_metainfo]
                WHERE name=:name
                """, binds)
