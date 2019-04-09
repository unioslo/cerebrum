# -*- coding: utf-8 -*-
# Copyright 2019 University of Oslo, Norway
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
"""
Implementation of mod_legacy_users.

The legacy_users module provides a list of reserved? usernames at UiT.

.. important::
   Do not use this module for anything else!


History
-------
This submodule used to live in Cerebrum.modules.no.uit.Account.
It was moved to a separate module after:

    commit b09f87aca4a1b6ed715f863dd7cf8730465391a3
    Merge: e940e928e ddf367002
    Date:  Tue Mar 26 12:18:52 2019 +0100

Note that the file location at the time was uit-modules/Account.py
"""
import logging

import six

from Cerebrum import Errors
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Utils import argument_to_sql, NotSet, prepare_string

__version__ = '1.0'

logger = logging.getLogger(__name__)


class LegacyUsers(DatabaseAccessor):
    """
    Access to the legacy_users table.
    """

    def __insert(self, username, values):
        """
        Insert a new row in the legacy_users table.
        """
        if 'source' not in values:
            raise ValueError("Missing required 'source' for new legacy user")
        if 'type' not in values:
            raise ValueError("Missing required 'type' for new legacy user")

        binds = {}
        binds.update(values)
        binds.update({'user_name': six.text_type(username)})

        stmt = """
          INSERT INTO [:table schema=cerebrum name=legacy_users]
          ({cols}) VALUES ({params})
        """.format(
            cols=', '.join(sorted(binds)),
            params=', '.join(':' + k for k in sorted(binds)))
        logger.debug('Inserting legacy_users username=%r columns=%r',
                     username, tuple(values.keys()))
        self.execute(stmt, binds)

    def __update(self, username, values):
        """
        Update an existing row in the legacy_users table.
        """
        if 'source' in values and not values['source']:
            raise ValueError("Cannot clear required 'source' for legacy user")
        if 'type' in values and not values['type']:
            raise ValueError("Cannot clear required 'type' for legacy user")

        binds = {}
        binds.update(values)
        binds.update({'user_name': six.text_type(username)})

        stmt = """
          UPDATE [:table schema=cerebrum name=legacy_users]
          SET {assign}
          WHERE user_name = :user_name
        """.format(assign=', '.join(k + '=:' + k for k in sorted(values)))
        logger.debug('Updating legacy_users username=%r columns=%r',
                     username, tuple(values.keys()))
        self.execute(stmt, binds)

    def exists(self, username):
        """ Check if username exists. """
        if not username:
            raise ValueError("No username given")
        binds = {'username': six.text_type(username)}
        stmt = """
          SELECT EXISTS (
            SELECT 1
            FROM [:table schema=cerebrum name=legacy_users]
            WHERE user_name = :username
          )
        """
        return self.query_1(stmt, binds)

    def get(self, username):
        """
        Get entry for a given username.
        """
        if not username:
            raise ValueError("No username given")
        binds = {'username': six.text_type(username)}
        stmt = """
            SELECT user_name, ssn, source, type, comment, name
            FROM [:table schema=cerebrum name=legacy_users]
            WHERE user_name = :username
        """
        return self.query_1(stmt, binds)

    def set(self, username, ssn=NotSet, source=NotSet, type=NotSet,
            comment=NotSet, name=NotSet):
        """
        Add or update a given legacy username.

        Will only update given columns - to clear a column, set its value to
        ``None``.

        :type username: str
        :param username:
            Insert or update username.

        :type ssn: str
        :param ssn:
            Set a norwegian national id for the owner of this username.

        :type source: str
        :param source:
            Set source of this username. Note that all entries *must* have a
            non-null source value.

        :type type: str
        :param source:
            Set type of username. Note that all entries *must* have a non-null
            type value.

        :type comment: str
        :param comment:
            Set a comment for this entry.

        :type name: str
        :param name:
            Set a name for the owner of this username.
        """
        try:
            old_values = self.get(username)
            is_new = False
        except Errors.NotFoundError:
            old_values = {}
            is_new = True

        new_values = {}

        def update_param(k, v):
            if v is NotSet or (k in old_values and v == old_values[k]):
                return
            new_values[k] = v

        update_param('ssn', ssn)
        update_param('source', source)
        update_param('type', type)
        update_param('comment', comment)
        update_param('name', name)

        if not new_values:
            logger.debug('No change in legacy_users user_name=%r', username)
            return

        if is_new:
            self.__insert(username, new_values)
        else:
            self.__update(username, new_values)

    def delete(self, username):
        """
        Delete a username entry from legacy_users.

        :type username: str
        :param username: The username to remove.
        """
        if not self.exists(username):
            raise Errors.NotFoundError("No legacy username %s" %
                                       repr(username))
        binds = {'username': six.text_type(username)}
        stmt = """
            DELETE FROM [:table schema=cerebrum name=legacy_users]
            WHERE user_name = :username
        """
        logger.debug('Deleting legacy_users user_name=%r', username)
        self.execute(stmt, binds)

    def search(self, username=None, ssn=None, source=None, type=None,
               comment=None, name=None):
        """
        Search for legacy usernames.

        :type user_name: str
        :param user_name: Find entries matching this username.

        :type ssn: str
        :param ssn: Find entry matching this norwegian national id.

        :type source: str
        :param source: Find entries matching this source.

        :type type: str
        :param source: Find entries matching this type.

        :type comment: str
        :param comment: Find entries with this comment. Supports wildcards.

        :type name: str
        :param name: Find entries with this owner name. Supports wildcards.
        """
        filters = []
        binds = dict()

        if username:
            filters.append(
                argument_to_sql(username, 'user_name', binds))
        if ssn:
            filters.append(
                argument_to_sql(ssn, 'ssn', binds))
        if source:
            filters.append(
                argument_to_sql(source, 'source', binds))
        if type:
            filters.append(
                argument_to_sql(type, 'type', binds))
        if comment:
            filters.append('comment like :comment')
            binds['comment'] = prepare_string(comment)
        if name:
            filters.append('name like :name')
            binds['name'] = prepare_string(name)

        where = ('WHERE ' + ' AND '.join(filters)) if filters else ''

        stmt = """
          SELECT user_name, ssn, source, type, comment, name
          FROM [:table schema=cerebrum name=legacy_users]
          {where}
        """.format(where=where)
        return self.query(stmt, binds)
