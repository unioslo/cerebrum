# -*- coding: utf-8 -*-
#
# Copyright 2002-2024 University of Oslo, Norway
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
Database queries for the account_authentication tables.

.. important::
   These queries does *not* log any audit records when setting or deleting
   auth methods.

   As each account authentication method represents the *same*
   plaintext password, we only log *one* event whenever we update account
   authentication method.  The caller needs to perform the neccessary
   changelog calls.

   Note also that there's only *one* change-type related to passwords - and
   that's the *account_password:set* change-type.  This should be set whenever
   a new password is stored, but there is no change-type for *removing* the
   password or authentication data for a given account.

.. todo::
   The ``Account.set_password()`` (or, really the password-related bits of
   ``Account.write_db()``), should probably be moved to a separate
   ``Cerebrum.auth`` submodule.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

from Cerebrum.Utils import Factory
from Cerebrum.Utils import argument_to_sql

logger = logging.getLogger(__name__)


DEFAULT_FIELDS = ("account_id", "method", "auth_data")
DEFAULT_ORDER = ("account_id", "method")


def legacy_list_authentication(db, method=None, filter_expired=True,
                               account_id=None, spread=None):
    """
    List all matching accounts and names, along with their auth details.

    This is a re-implementation of Account.list_account_authentication().  This
    method is a bit weird (and potentially a lot more expensive than what's
    usually needed) as it does a LEFT JOIN.  When filtering by multiple
    spreads, you may get a lot of duplicate rows.

    :param method: one or more auth methods to list (defaults to MD5-crypt)
    :param bool filter_expired: exclude expired accounts (default)
    :param account_id: only include the specified accounts
    :param spread: only include accounts with one or more of the given spreads
    """
    binds = {}
    tables = []
    where = []
    const = Factory.get("Constants")(db)
    if method is None:
        method = const.auth_type_md5_crypt
    aa_method = argument_to_sql(method, "aa.method", binds, int)
    if spread is not None:
        tables.append("[:table schema=cerebrum name=entity_spread] es")
        where.append("ai.account_id=es.entity_id")
        where.append(argument_to_sql(spread, "es.spread", binds, int))
        where.append(argument_to_sql(const.entity_account,
                                     "es.entity_type", binds, int))
    if filter_expired:
        where.append("(ai.expire_date IS NULL OR ai.expire_date > [:now])")
    if account_id:
        where.append(argument_to_sql(account_id, "ai.account_id",
                                     binds, int))
    where.append("ai.account_id=en.entity_id")
    where = " AND ".join(where)
    if tables:
        tables = ",".join(tables) + ","
    else:
        tables = ""

    return db.query(
        """
          SELECT
            ai.account_id, en.entity_name, aa.method, aa.auth_data
          FROM
            {tables}
            [:table schema=cerebrum name=entity_name] en,
            [:table schema=cerebrum name=account_info] ai
          LEFT JOIN
            [:table schema=cerebrum name=account_authentication] aa
            ON ai.account_id=aa.account_id
            AND {method}
          WHERE {where}
        """.format(tables=tables, method=aa_method, where=where),
        binds,
    )


def _select(account_id=None, method=None, auth_data=None, _prefix=""):
    """
    Generate clauses and binds for account_authentication queries.

    :param account_id: only include results for these entities
    :param method: only include results for these auth methods
    :param auth_data: not currently supported (TODO)

    :param _prefix:
        A prefix for entity_trait column names.

        A prefix is needed when querying multiple tables, and a column in
        entity_trait may conflict with column names from another table.

    :rtype: tuple(list, dict)
    :returns:
        Returns a list of conditions, and a dict of query params.
    """
    p = "{}.".format(_prefix.rstrip(".")) if _prefix else ""
    clauses = []
    binds = {}

    #
    # mandatory value selects (columns that doesn't allow None)
    #
    if account_id is not None:
        clauses.append(
            argument_to_sql(account_id, p + "account_id", binds, int))
    if method is not None:
        clauses.append(
            argument_to_sql(method, p + "method", binds, int))
    if auth_data is not None:
        raise NotImplementedError("select by auth_data not supported")

    return clauses, binds


def list_authentication(db, account_id=None, method=None,
                        filter_expired=True, fetchall=True):
    """
    List account authentication data.

    :param account_id: filter results by one or more account ids
    :param method: filter results by one or more auth methods
    :param filter_expired: do not include expired accounts (default)
    """
    conds, binds = _select(account_id=account_id, method=method, _prefix="aa")
    if filter_expired:
        conds.append("(ai.expire_date IS NULL OR ai.expire_date > [:now])")
    stmt = """
      SELECT
        {columns}
      FROM
        [:table schema=cerebrum name=account_info] ai
      JOIN
        [:table schema=cerebrum name=account_authentication] aa
      ON
        ai.account_id = aa.account_id
      {where}
      ORDER BY {order}
    """.format(
        columns=", ".join("aa." + c for c in DEFAULT_FIELDS),
        order=", ".join("aa." + c for c in DEFAULT_ORDER),
        where=("WHERE " + " AND ".join(conds)) if conds else "",
    )
    return db.query(stmt, binds, fetchall=fetchall)


def list_authentication_methods(db, account_id=None, method=None):
    """
    Get account authentication methods.

    :param account_id: filter results by one or more account ids
    :param method: filter results by one or more auth methods
    """
    conds, binds = _select(account_id=account_id, method=method)
    stmt = """
      SELECT DISTINCT method
      FROM [:table schema=cerebrum name=account_authentication]
      {where}
      ORDER BY method
    """.format(
        where=("WHERE " + " AND ".join(conds)) if conds else "",
    )
    return db.query(stmt, binds, fetchall=True)


def get_authentication(db, account_id, method):
    """
    Get account authentication data.

    :param account_id: account id to get data for
    :param method: authentication medhod to get data for
    """
    return db.query_1(
        """
          SELECT auth_data
          FROM [:table schema=cerebrum name=account_authentication]
          WHERE account_id=:account_id
            AND method=:method
        """,
        {
            'account_id': int(account_id),
            'method': int(method),
        },
    )


def authentication_method_exists(db, account_id, method):
    """ Check if a given auth method exists for a given account. """
    binds = {
        'account_id': int(account_id),
        'method': int(method),
    }
    stmt = """
      SELECT EXISTS (
        SELECT 1
        FROM
          [:table schema=cerebrum name=account_authentication]
        WHERE
          account_id=:account_id AND
          method=:method
      )
    """
    return db.query_1(stmt, binds)


def set_authentication(db, account_id, method, auth_data):
    binds = {
        'account_id': int(account_id),
        'method': int(method),
        'auth_data': auth_data,
    }
    exists = authentication_method_exists(db, account_id, method)
    if exists:
        # auth_data *may* have the same value, but we don't want to reveal that
        # through e.g. logs, so we update without checking if it's neccessary.
        row = db.query_1(
            """
              UPDATE
                [:table schema=cerebrum name=account_authentication]
              SET
                auth_data=:auth_data
              WHERE
                account_id=:account_id AND
                method=:method
              RETURNING
                {columns}
            """.format(columns=", ".join(DEFAULT_FIELDS)),
            binds,
        )
        logger.info("updated auth method=%r for account_id=%r",
                    row['method'], row['account_id'])
    else:
        row = db.query_1(
            """
              INSERT INTO
                [:table schema=cerebrum name=account_authentication]
                (account_id, method, auth_data)
              VALUES
                (:account_id, :method, :auth_data)
              RETURNING
                {columns}
            """.format(columns=", ".join(DEFAULT_FIELDS)),
            binds,
        )
        logger.info("added auth method=%r to account_id=%r",
                    row['method'], row['account_id'])
    return row


def delete_authentication(db, account_id, method=None):
    """
    Delete account authentication data.

    :type account_id: int
    :type method: NoneType, int or sequence of ints

    :returns: deleted db-rows
    """
    conds, binds = _select(account_id=int(account_id), method=method)
    stmt = """
      DELETE FROM
        [:table schema=cerebrum name=account_authentication]
      WHERE
        {conds}
      RETURNING
        {columns}
    """.format(
        conds=" AND ".join(conds),
        columns=", ".join(DEFAULT_FIELDS),
    )
    rows = db.query(stmt, binds, fetchall=True)
    for row in rows:
        logger.info("deleted auth method=%r for entity_id=%r",
                    row['method'], row['account_id'])
    return rows
