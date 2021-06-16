# -*- coding: utf-8 -*-
#
# Copyright 2021 University of Oslo, Norway
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
Database access to personal otp secrets.

This module contains all the neccessary queries for fetching and modifying otp
secrets in the database.
"""
import logging

import six

import Cerebrum.Errors
from Cerebrum.Utils import argument_to_sql

from .constants import OtpChangeTypeConstants


# default row order in query results
DEFAULT_ORDER = ('person_id', 'otp_type', 'created_at')

# default fields and field order in query results
DEFAULT_FIELDS = ('person_id', 'otp_type', 'otp_payload', 'created_at')


logger = logging.getLogger(__name__)


def _select(person_id=None, otp_type=None,
            created_before=None, created_after=None):
    """
    Generate clauses and binds for person_otp_secret queries.

    :param person_id: only include results for these persons
    :param otp_type: only include results for these otp types
    :param created_before:
        only include results with a created_at before this value
    :param created_after:
        only include results with a created_at after this value

    :rtype: tuple(list, dict)
    :returns:
        Returns a list of conditions, and a dict of query params.
    """
    clauses = []
    binds = {}

    # value selects:

    if person_id is not None:
        clauses.append(
            argument_to_sql(person_id, 'person_id', binds, int))
    if otp_type is not None:
        clauses.append(
            argument_to_sql(otp_type, 'otp_type', binds, six.text_type))

    # range selects:

    if created_before and created_after and created_before < created_after:
        # a date can never be *both* before <t> *and* after that same
        # <t>+<delta>
        raise ValueError("created_after: cannot be after created_before"
                         " (%s < created < %s)" %
                         (created_after, created_before))

    if created_before is not None:
        clauses.append("created_at < :created_b")
        binds['created_b'] = created_before
    if created_after is not None:
        clauses.append("created_at > :created_a")
        binds['created_a'] = created_after

    return clauses, binds


def sql_search(db, fetchall=True, limit=None, **selects):
    """
    Search personal otp secrets by person or secret type

    See py:func:`._select` for search params.

    :param fetchall: see ``Cerebrum.database.Database.query``

    :returns: matching rows.
    """
    query = """
      SELECT {fields}
      FROM [:table schema=cerebrum name=person_otp_secret]
      {where}
      ORDER BY {order}
      {limit}
    """
    clauses, binds = _select(**selects)

    if limit is None:
        limit_clause = ''
    else:
        limit_clause = 'LIMIT :limit'
        binds['limit'] = int(limit)

    if clauses:
        where = ' WHERE ' + ' AND '.join(clauses)
    else:
        where = ''

    return db.query(
        query.format(
            fields=', '.join(DEFAULT_FIELDS),
            where=where,
            order=', '.join(DEFAULT_ORDER),
            limit=limit_clause,
        ),
        binds,
        fetchall=fetchall,
    )


def sql_delete(db, **selects):
    """
    Delete personal otp secrets.

    See py:func:`._select` for filter params.

    :returns: deleted rows.
    """
    stmt = """
      DELETE FROM [:table schema=cerebrum name=person_otp_secret]
      {where}
      RETURNING {fields}
    """
    clauses, binds = _select(**selects)

    if clauses:
        where = ' WHERE ' + ' AND '.join(clauses)
    else:
        where = ''

    deleted_rows = db.query(
        stmt.format(
            where=where,
            order=', '.join(DEFAULT_ORDER),
            fields=', '.join(DEFAULT_FIELDS),
        ),
        binds,
        fetchall=True,
    )
    for row in deleted_rows:
        logger.info('removed otp type=%r from person_id=%r',
                    row['otp_type'], row['person_id'])
        db.log_change(
            subject_entity=row['person_id'],
            change_type_id=OtpChangeTypeConstants.person_otp_del,
            destination_entity=None,
            change_params={'otp_type': row['otp_type']},
        )
    return deleted_rows


def sql_clear(db, person_id, otp_type):
    """
    Remove a personal otp secret row by primary key.

    :returns: the deleted row

    :raises NotFoundError: if no matching item exist
    """
    rows = list(sql_delete(db, person_id=int(person_id),
                           otp_type=six.text_type(otp_type)))
    if len(rows) < 1:
        raise Cerebrum.Errors.NotFoundError(
            'no otp secret of type=%s for person_id=%s' %
            (otp_type, person_id))

    if len(rows) > 1:
        raise Cerebrum.Errors.TooManyRowsError(
            'multiple (%d) otp secrets of type=%s for person_id=%s' %
            (len(rows), otp_type, person_id))

    item = rows[0]
    return item


def sql_get(db, person_id, otp_type):
    """
    Get a personal otp secret row by primary key

    :returns: the found row

    :raises NotFoundError: if no matching row exist
    """
    rows = list(sql_search(db, person_id=int(person_id),
                           otp_type=six.text_type(otp_type)))
    if len(rows) < 1:
        raise Cerebrum.Errors.NotFoundError(
            'no otp secret of type=%s for person_id=%s' %
            (otp_type, person_id))

    if len(rows) > 1:
        raise Cerebrum.Errors.TooManyRowsError(
            'multiple otp secrets of type=%s for person_id=%s' %
            (otp_type, person_id))

    return rows[0]


def _sql_insert(db, person_id, otp_type, otp_payload, created_at=None):
    """ Insert a new personal otp secret. """
    binds = {
        'person_id': int(person_id),
        'otp_type': six.text_type(otp_type),
        'otp_payload': six.text_type(otp_payload),
    }

    if created_at is not None:
        # we really shouldn't ever need to set this value
        binds['created_at'] = created_at

    stmt = """
      INSERT INTO [:table schema=cerebrum name=person_otp_secret]
        ({cols})
      VALUES
        ({binds})
      RETURNING {fields}
    """.format(
        cols=', '.join(sorted(binds)),
        binds=', '.join(':' + col for col in sorted(binds)),
        fields=', '.join(DEFAULT_FIELDS),
    )
    row = db.query_1(stmt, binds)
    logger.info('added otp type=%r to person_id=%r',
                row['otp_type'], row['person_id'])
    db.log_change(
        subject_entity=row['person_id'],
        change_type_id=OtpChangeTypeConstants.person_otp_add,
        destination_entity=None,
        change_params={'otp_type': row['otp_type']},
    )
    return row


def _sql_update(db, person_id, otp_type, otp_payload=None, created_at=None):
    """ Update an existing personal otp secret. """
    binds = {
        'person_id': int(person_id),
        'otp_type': six.text_type(otp_type),
    }

    update = {}

    if otp_payload is not None:
        update['otp_payload'] = six.text_type(otp_payload)

    if created_at is not None:
        update['created_at'] = created_at

    if not update:
        raise TypeError('missing otp_payload or created_at value to update')

    binds.update(update)

    stmt = """
      UPDATE [:table schema=cerebrum name=person_otp_secret]
      SET
        {changes}
      WHERE
        person_id = :person_id AND otp_type = :otp_type
      RETURNING {fields}
    """.format(
        changes=', '.join('{0} = :{0}'.format(k) for k in sorted(update)),
        fields=', '.join(DEFAULT_FIELDS),
    )
    row = db.query_1(stmt, binds)
    logger.info('updated otp type=%r on person_id=%r',
                row['otp_type'], row['person_id'])
    db.log_change(
        subject_entity=row['person_id'],
        change_type_id=OtpChangeTypeConstants.person_otp_mod,
        destination_entity=None,
        change_params={'otp_type': row['otp_type']},
    )
    return row


def sql_set(db, person_id, otp_type, otp_payload, created_at=None):
    """
    Add or update a personal otp secret.

    :param db:
    :param person_id: entity_id of an existing person
    :param otp_type: otp_type to set
    :param otp_payload: secret to set
    :param created_at: create/update time for this item
    """

    try:
        prev = sql_get(db, person_id, otp_type)
    except Cerebrum.Errors.NotFoundError:
        prev = dict()

    values = {}

    if otp_payload != prev.get('otp_payload'):
        values['otp_payload'] = otp_payload

    if created_at and created_at != prev.get('created_at'):
        values['created_at'] = created_at

    if prev:
        if values:
            # update the given key/value pairs
            return _sql_update(db, person_id, otp_type, **values)
        else:
            # no change - should not happen normally
            logger.warning('no change in sql_set on person_id=%r, otp_type=%r',
                           person_id, otp_type)
            return None
    else:
        return _sql_insert(db, person_id, otp_type, **values)


def sql_get_otp_type_count(db, **kwargs):
    """
    Get otp row counts by otp_type.

    See py:func:`._select` for filtering params.

    :returns: rows of (queue, count) tuples
    """
    query = """
      SELECT otp_type, count(*) as num
      FROM [:table schema=cerebrum name=person_otp_secret]
      {where}
      GROUP BY otp_type
      ORDER BY otp_type
    """
    clauses, binds = _select(**kwargs)

    if clauses:
        where = ' WHERE ' + ' AND '.join(clauses)
    else:
        where = ''

    return db.query(query.format(where=where), binds, fetchall=True)
