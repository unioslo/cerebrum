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
Implementation of mod_apikeys database access.
"""
import logging

import six

from Cerebrum import Errors
from Cerebrum.DatabaseAccessor import DatabaseAccessor

logger = logging.getLogger(__name__)


class ApiKeys(DatabaseAccessor):

    def __insert(self, account_id, value):
        """
        Insert a new row in the apikey table.
        """
        binds = {
            'account_id': int(account_id),
            'value': six.text_type(value),
        }
        stmt = """
          INSERT INTO [:table schema=cerebrum name=account_apikey]
            (account_id, value)
          VALUES
            (:account_id, :value)
        """
        logger.debug('inserting apikey for account_id=%r', account_id)
        self.execute(stmt, binds)
        # TODO: change_log

    def __update(self, account_id, value):
        """
        Update a row in the apikey table.
        """
        binds = {
            'account_id': int(account_id),
            'value': six.text_type(value),
        }
        stmt = """
          UPDATE [:table schema=cerebrum name=account_apikey]
          SET value = :value
          WHERE account_id = :account_id
        """
        logger.debug('updating apikey for account_id=%r', account_id)
        self.execute(stmt, binds)
        # TODO: change_log

    def exists(self, account_id):
        """
        Check if there exists an apikey for a given account.
        """
        if not account_id:
            raise ValueError("missing account_id")
        binds = {
            'account_id': int(account_id),
        }
        stmt = """
          SELECT EXISTS (
            SELECT 1
            FROM [:table schema=cerebrum name=account_apikey]
            WHERE account_id = :account_id
          )
        """
        return self.query_1(stmt, binds)

    def get(self, account_id):
        """
        Get apikey value for a given account.

        :rtype: six.text_type

        :raises ValueError: if no account_id is given
        :raises Cerebrum.Errors.NotFoundError: if no apikey exists
        """
        if not account_id:
            raise ValueError("missing account_id")
        binds = {
            'account_id': int(account_id),
        }
        stmt = """
          SELECT value
          FROM [:table schema=cerebrum name=account_apikey]
          WHERE account_id = :account_id
        """
        return self.query_1(stmt, binds)

    def set(self, account_id, value):
        try:
            old_value = self.get(account_id)
            is_new = False
        except Errors.NotFoundError:
            old_value = None
            is_new = True

        if not is_new and old_value == value:
            return

        if is_new:
            self.__insert(account_id, value)
        else:
            self.__update(account_id, value)

    def delete(self, account_id):
        """
        Delete apikey value for a given account.
        """
        if not account_id:
            raise ValueError("missing account_id")
        binds = {
            'account_id': int(account_id),
        }
        stmt = """
          DELETE FROM [:table schema=cerebrum name=account_apikey]
          WHERE account_id = :account_id
        """
        logger.debug('deleting apikey for account_id=%r', account_id)
        return self.execute(stmt, binds)
        # TODO: change_log

    def map(self, value):
        """
        Get account_id for a given apikey.
        """
        if not value:
            raise ValueError("missing value")
        binds = {
            'value': six.text_type(value),
        }
        stmt = """
          SELECT account_id
          FROM [:table schema=cerebrum name=account_apikey]
          WHERE value = :value
        """
        return self.query_1(stmt, binds)

    def search(self, account_id=None, value=None):
        pass
