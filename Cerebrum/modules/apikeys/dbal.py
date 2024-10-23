# -*- coding: utf-8 -*-
#
# Copyright 2019-2024 University of Oslo, Norway
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
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

import six

from Cerebrum import Errors
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Utils import NotSet, argument_to_sql
from Cerebrum.database import query_utils

from .constants import CLConstants

logger = logging.getLogger(__name__)


# Result ordering in query results
DEFAULT_ORDER = ('updated_at', 'account_id', 'identifier')

# Fields and field order in apikeys query results
DEFAULT_FIELDS = ('identifier', 'account_id', 'description', 'updated_at')


class ApiMapping(DatabaseAccessor):

    def __insert(self, identifier, account_id, description):
        """
        Insert a new row in the apikey table.
        """
        binds = {
            'identifier': six.text_type(identifier),
            'account_id': int(account_id),
            'description': six.text_type(description) if description else None,
        }
        stmt = """
          INSERT INTO [:table schema=cerebrum name=apikey_client_map]
            (identifier, account_id, description)
          VALUES
            (:identifier, :account_id, :description)
          RETURNING
            {fields}
        """.format(fields=", ".join(DEFAULT_FIELDS))
        row = self.query_1(stmt, binds)
        logger.debug('added apikey for account_id=%d, identifier=%s',
                     repr(row['account_id']), repr(row['identifier']))
        self._db.log_change(
            row['account_id'],
            CLConstants.apikey_add,
            None,
            change_params={'identifier': row['identifier']},
        )
        return row

    def __update(self, identifier, account_id, description):
        """
        Update a row in the apikey table.
        """
        binds = {
            'identifier': six.text_type(identifier),
            'account_id': int(account_id),
            'description': six.text_type(description) if description else None,
        }
        stmt = """
          UPDATE [:table schema=cerebrum name=apikey_client_map]
          SET description = :description,
              account_id = :account_id
          WHERE
            identifier = :identifier
          RETURNING
            {fields}
        """.format(fields=", ".join(DEFAULT_FIELDS))
        row = self.query_1(stmt, binds)
        logger.debug('updated apikey for account_id=%s, identifier=%s',
                     repr(row['account_id']), repr(row['identifier']))
        self._db.log_change(
            row['account_id'],
            CLConstants.apikey_mod,
            None,
            change_params={'identifier': row['identifier']},
        )
        return row

    def exists(self, identifier):
        """
        Check if there exists an apikey for a given account.
        """
        if not identifier:
            raise ValueError("missing identifier")
        binds = {
            'identifier': six.text_type(identifier),
        }
        stmt = """
          SELECT EXISTS (
            SELECT 1
            FROM [:table schema=cerebrum name=apikey_client_map]
            WHERE
              identifier = :identifier
          )
        """
        return self.query_1(stmt, binds)

    def get(self, identifier):
        """
        Get apikey value for a given account.

        :rtype: six.text_type

        :raises ValueError: if no account_id is given
        :raises Cerebrum.Errors.NotFoundError: if no apikey exists
        """
        if not identifier:
            raise ValueError("missing identifier")
        binds = {
            'identifier': six.text_type(identifier),
        }
        binds = {
            'identifier': six.text_type(identifier),
        }
        stmt = """
          SELECT {fields}
          FROM [:table schema=cerebrum name=apikey_client_map]
          WHERE
            identifier = :identifier
        """.format(fields=", ".join(DEFAULT_FIELDS))
        return self.query_1(stmt, binds)

    def set(self, identifier, account_id, description=None):
        try:
            old_values = self.get(identifier)
            is_new = False
        except Errors.NotFoundError:
            old_values = {}
            is_new = True

        if not is_new and old_values['account_id'] != account_id:
            raise ValueError(
                'Identifier=%r is already assigned to account_id=%r' %
                (identifier, account_id))

        if not is_new and old_values['description'] == description:
            return old_values

        if is_new:
            return self.__insert(identifier, account_id, description)
        else:
            return self.__update(identifier, account_id, description)

    def delete(self, identifier):
        """
        Delete apikey value for a given account.
        """
        binds = {'identifier': identifier}
        stmt = """
          DELETE FROM [:table schema=cerebrum name=apikey_client_map]
          WHERE
            identifier = :identifier
          RETURNING
            {fields}
        """.format(fields=", ".join(DEFAULT_FIELDS))
        row = self.query_1(stmt, binds)
        logger.debug('deleted apikey for account_id=%r, identifier=%r',
                     row['account_id'], row['identifier'])
        self._db.log_change(
            row['account_id'],
            CLConstants.apikey_mod,
            None,
            change_params={'identifier': row['identifier']},
        )
        return row

    def search(self, identifier=None, account_id=None,
               description=NotSet,
               description_like=None,
               description_ilike=None):
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
        if identifier is not None:
            filters.append(
                argument_to_sql(identifier, 'identifier', binds,
                                six.text_type))
        desc_cond, desc_bind = query_utils.pattern_helper(
            "description",
            value=description,
            case_pattern=description_like,
            icase_pattern=description_ilike,
            nullable=True,
        )
        if desc_cond:
            filters.append(desc_cond)
            binds.update(desc_bind)

        stmt = """
          SELECT {fields}
          FROM [:table schema=cerebrum name=apikey_client_map]
          {where}
          ORDER BY {order}
        """.format(
            fields=", ".join(DEFAULT_FIELDS),
            order=", ".join(DEFAULT_ORDER),
            where=('WHERE ' + ' AND '.join(filters)) if filters else '',
        )
        return self.query(stmt, binds)
