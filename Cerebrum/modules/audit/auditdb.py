# -*- coding: utf-8 -*-
#
# Copyright 2018-2023 University of Oslo, Norway
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
Database access to audit records.

Audit records should mostly be read or appended to the database.  In the future
there may be cleanup scripts that clear out non-critical personal information
from audit record params, and delete really old audit records, subject to data
retention.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    # TODO: unicode_literals,
)
import datetime
import json

from Cerebrum.database import query_utils
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Utils import argument_to_sql, Factory
from Cerebrum.utils import date_compat
from Cerebrum.utils.date import apply_timezone

from .record import DbAuditRecord


def _serialize_datetime(dt):
    if dt is None:
        return None
    if isinstance(dt, datetime.datetime) and not dt.tzinfo:
        dt = apply_timezone(dt)
    return dt.isoformat()


def _serialize_mx_datetime(dt):
    """ Convert mx-like objects to string. """
    if date_compat.is_mx_date(dt):
        return _serialize_datetime(dt.pydate())
    elif dt:
        return _serialize_datetime(dt.pydatetime())
    else:
        return None


def serialize_params(value):
    # TODO: We should'd need to do this -- it would be better to ensure that
    # all change_params are properly serialized when calling log_change()
    if isinstance(value, datetime.date):
        return _serialize_datetime(value)
    elif date_compat.is_mx_datetime(value):
        return _serialize_mx_datetime(value)
    elif isinstance(value, (list, tuple, set)):
        return [serialize_params(p) for p in value]
    elif isinstance(value, dict):
        return {k: serialize_params(value[k]) for k in value}
    else:
        return value


def sql_get_record(db, record_id):
    query = """
      SELECT *
      FROM [:table schema=cerebrum name=audit_log]
      WHERE record_id = :record_id
    """
    binds = {
        'record_id': int(record_id),
    }
    return db.query_1(query, binds)


def _select(change_types=None, operators=None, entities=None, targets=None,
            record_ids=None, after_id=None, before_id=None,
            after_timestamp=None, before_timestamp=None):
    """
    Generate clauses and binds for audit log queries.

    Example:

        >>> _select(entities=(123, 124), operators=2)
        (
            ['entity IN (:entity0, :entity1)', 'operator = :operator'],
            {'entity0': 123, 'entity1': 124, 'operator': 2},
        )

    :param change_types: only include results for these change types
    :param operators: only include results for these operator ids
    :param entities: only include results for these subject entity ids
    :param targets: only include results for these destination entity ids
    :param record_ids: only include these record ids (*)
    :param after_id: only include record ids bigger than this (*)
    :param before_id: only include record ids smaller than this (*)
    :param timestamp_before: only include results with a timetsamp before this
    :param timestamp_after: only include results with a timestamp after this

    Note:
        If both timestamp_before and _after is given, they must be comparable.

    Note:
        If both record_ids and after_id/before_id is given, they are OR-ed.

    :rtype: tuple(list, dict)
    :returns:
        Returns a list of conditions, and a dict of query params.
    """
    clauses = []
    binds = {}

    # value selects
    if change_types:
        clauses.append(
            argument_to_sql(change_types, 'change_type', binds, int))
    if operators:
        clauses.append(
            argument_to_sql(operators, 'operator', binds, int))
    if entities:
        clauses.append(
            argument_to_sql(entities, 'entity', binds, int))
    if targets:
        clauses.append(
            argument_to_sql(targets, 'target', binds, int))

    # timestamp_before/timestamp_after
    ts_cond, ts_binds = query_utils.date_helper("timestamp",
                                                gt=after_timestamp,
                                                lt=before_timestamp)
    if ts_cond:
        clauses.append(ts_cond)
        binds.update(ts_binds)

    # record_ids/before_id/after_id
    id_cond, id_binds = query_utils.int_helper("record_id",
                                               value=record_ids,
                                               gt=after_id,
                                               lt=before_id)
    if id_cond:
        clauses.append(id_cond)
        binds.update(id_binds)

    return clauses, binds


def sql_search(db, **kwargs):
    """
    Search for audit records.

    :see: `._select` for arguments.
    """
    query = """
      SELECT *
      FROM [:table schema=cerebrum name=audit_log]
    """
    fetchall = kwargs.pop("fetchall", False)
    clauses, binds = _select(**kwargs)

    if clauses:
        where = " WHERE " + " AND ".join(clauses)
    else:
        where = ""

    return db.query(query + where, binds, fetchall=fetchall)


def sql_insert(
        db, change_type, operator_id, entity_id,
        target_id=None,
        metadata=None,
        params=None,
        timestamp=None,
        record_id=None):
    binds = {
        'change_type': int(change_type),
        'operator': int(operator_id),
        'entity': int(entity_id),
    }
    if timestamp:
        binds['timestamp'] = timestamp

    if record_id:
        binds['record_id'] = int(record_id)
    else:
        binds['record_id'] = int(db.nextval('audit_log_seq'))

    if target_id:
        binds['target'] = int(target_id)

    if metadata:
        binds['metadata'] = json.dumps(metadata)

    if params:
        binds['params'] = json.dumps(serialize_params(params))

    insert = """
    INSERT INTO [:table schema=cerebrum name=audit_log]
        ({fields})
        VALUES ({binds})
    """.format(
        fields=', '.join(sorted(binds)),
        binds=', '.join(':' + field
                        for field in sorted(binds)))
    db.execute(insert, binds)
    return binds['record_id']


def sql_delete(db, **kwargs):
    """
    Delete audit records.

    .. note::
        This should generally never be done, as audit records should be
        peristent.

    .. warning::
        By giving no filter arguments, all audit records will be deleted.

    :see: `._select` for filter arguments.
    """
    query = """
      DELETE FROM [:table schema=cerebrum name=audit_log]
    """
    clauses, binds = _select(**kwargs)

    if clauses:
        where = " WHERE " + " AND ".join(clauses)
    else:
        where = ""

    return db.execute(query + where, binds)


def db_row_to_record(db, row):
    clconst = Factory.get('CLConstants')(db)
    row = dict(row)
    row['change_type'] = clconst.ChangeType(row['change_type'])
    return DbAuditRecord.from_dict(row)


class AuditLogAccessor(DatabaseAccessor):
    # TODO: Read and write AuditRecord objects

    def get_by_id(self, record_id):
        return db_row_to_record(sql_get_record(self._db, record_id))

    def search(self, **fields):
        for row in sql_search(self._db, **fields):
            yield db_row_to_record(self._db, row)

    def append(self, record):
        # TODO: assert AuditRecord instance?
        return sql_insert(
            self._db,
            record.change_type,
            record.operator_id,
            record.entity_id,
            target_id=record.target_id,
            metadata=record.metadata,
            params=record.params,
            timestamp=record.timestamp,
            record_id=record.record_id)

    # def update(self, record):
    #     # TODO: assert DbAuditRecord instance?
    #     data = record.to_dict()
    #     return sql_update(self._db, **data)
