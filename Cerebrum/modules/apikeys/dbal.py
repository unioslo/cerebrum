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
from Cerebrum.Utils import argument_to_sql
from .constants import CLConstants

logger = logging.getLogger(__name__)


class ApiKeys(DatabaseAccessor):

    def __insert(self, account_id, label, value):
        """
        Insert a new row in the apikey table.
        """
        binds = {
            'account_id': int(account_id),
            'label': six.text_type(label),
            'value': six.text_type(value),
        }
        stmt = """
          INSERT INTO [:table schema=cerebrum name=account_apikey]
            (account_id, label, value)
          VALUES
            (:account_id, :label, :value)
        """
        logger.debug('inserting apikey for account_id=%r, label=%r',
                     account_id, label)
        self.execute(stmt, binds)
        self._db.log_change(int(account_id), CLConstants.apikey_add, None,
                            change_params={'label': six.text_type(label)})

    def __update(self, account_id, label, value):
        """
        Update a row in the apikey table.
        """
        binds = {
            'account_id': int(account_id),
            'label': six.text_type(label),
            'value': six.text_type(value),
        }
        stmt = """
          UPDATE [:table schema=cerebrum name=account_apikey]
          SET value = :value
          WHERE
            account_id = :account_id AND
            label = :label
        """
        logger.debug('updating apikey for account_id=%r, label=%r',
                     account_id, label)
        self.execute(stmt, binds)
        self._db.log_change(int(account_id), CLConstants.apikey_mod, None,
                            change_params={'label': six.text_type(label)})

    def exists(self, account_id, label):
        """
        Check if there exists an apikey for a given account.
        """
        if not account_id:
            raise ValueError("missing account_id")
        if not label:
            raise ValueError("missing label")
        binds = {
            'account_id': int(account_id),
            'label': six.text_type(label),
        }
        stmt = """
          SELECT EXISTS (
            SELECT 1
            FROM [:table schema=cerebrum name=account_apikey]
            WHERE
              account_id = :account_id AND
              label = :label
          )
        """
        return self.query_1(stmt, binds)

    def get(self, account_id, label):
        """
        Get apikey value for a given account.

        :rtype: six.text_type

        :raises ValueError: if no account_id is given
        :raises Cerebrum.Errors.NotFoundError: if no apikey exists
        """
        if not account_id:
            raise ValueError("missing account_id")
        if not label:
            raise ValueError("missing label")
        binds = {
            'account_id': int(account_id),
            'label': six.text_type(label),
        }
        stmt = """
          SELECT value
          FROM [:table schema=cerebrum name=account_apikey]
          WHERE
            account_id = :account_id AND
            label = :label
        """
        return self.query_1(stmt, binds)

    def set(self, account_id, label, value):
        try:
            old_value = self.get(account_id, label)
            is_new = False
        except Errors.NotFoundError:
            old_value = None
            is_new = True

        if not is_new and old_value == value:
            return

        if is_new:
            self.__insert(account_id, label, value)
        else:
            self.__update(account_id, label, value)

    def delete(self, account_id, label):
        """
        Delete apikey value for a given account.
        """
        if not account_id:
            raise ValueError("missing account_id")
        if not label:
            raise ValueError("missing label")
        if not self.exists(account_id, label):
            raise Errors.NotFoundError(
                'No apikey for account_id=%r with label=%r' %
                (account_id, label))
        binds = {
            'account_id': int(account_id),
            'label': six.text_type(label),
        }
        stmt = """
          DELETE FROM [:table schema=cerebrum name=account_apikey]
          WHERE
            account_id = :account_id AND
            label = :label
        """
        logger.debug('deleting apikey for account_id=%r', account_id)
        self.execute(stmt, binds)
        self._db.log_change(int(account_id), CLConstants.apikey_del, None,
                            change_params={'label': six.text_type(label)})

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
          SELECT account_id, label
          FROM [:table schema=cerebrum name=account_apikey]
          WHERE value = :value
        """
        return self.query_1(stmt, binds)

    def search(self, account_id=None, label=None, value=None):
        """
        Get apikey value for a given account.

        :rtype: six.text_type

        :raises ValueError: if no account_id is given
        :raises Cerebrum.Errors.NotFoundError: if no apikey exists
        """
        binds = {}
        filters = []
        if account_id is not None:
            filters.append(
                argument_to_sql(account_id, 'account_id', binds, int))
        if label is not None:
            filters.append(
                argument_to_sql(label, 'label', binds, six.text_type))
        if value is not None:
            filters.append(
                argument_to_sql(value, 'value', binds, six.text_type))

        stmt = """
          SELECT *
          FROM [:table schema=cerebrum name=account_apikey]
          {where}
        """.format(where=('WHERE ' + ' AND '.join(filters)) if filters else '')
        return self.query(stmt, binds)
