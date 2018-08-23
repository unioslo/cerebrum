#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2018 University of Oslo, Norway
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
""" Database access to audit records.

Audit records should mostly be read or appended to the database.  In the future
there may be cleanup scripts that clear out non-critical personal information
from audit record params, and delete really old audit records, subject to data
retention.
"""
import json

from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Utils import argument_to_sql, Factory

from .record import AuditRecord, DbAuditRecord


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


def sql_search(
        db,
        change_types=None,
        operators=None,
        entities=None,
        targets=None,
        record_ids=None,
        after_id=None, before_id=None,
        after_timestamp=None, before_timestamp=None,
        fetchall=True):
    """ TODO: document """
    query = """
    SELECT *
    FROM [:table schema=cerebrum name=audit_log]
    """
    clauses = []
    binds = {}

    #
    # value selects
    #
    if record_ids:
        clauses.append(
            argument_to_sql(record_ids, 'record_id', binds, int))
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

    #
    # range selects
    #
    if after_timestamp is not None:
        clauses.append("timestamp > :after_ts")
        binds['after_ts'] = after_timestamp
    if before_timestamp is not None:
        clauses.append("timestamp < :before_ts")
        binds['before_timestamp'] = before_timestamp
    if after_id is not None:
        clauses.append("record_id > :after_id")
        binds['after_id'] = int(after_id)
    if before_id is not None:
        clauses.append("record_id < :before_id")
        binds['before_id'] = int(before_id)

    if clauses:
        where = ' WHERE ' + ' AND '.join(clauses)
    else:
        where = ''

    return db.query(
        query + where,
        binds,
        fetchall=fetchall)


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
        binds['params'] = json.dumps(params)

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


def sql_delete(
        db,
        change_types=None,
        operators=None,
        entities=None,
        targets=None,
        record_ids=None,
        after_id=None, before_id=None,
        after_timestamp=None, before_timestamp=None):
    """ TODO: document """
    query = """
    DELETE FROM [:table schema=cerebrum name=audit_log]
    """
    clauses = []
    binds = {}

    #
    # value selects
    #
    if record_ids:
        clauses.append(
            argument_to_sql(record_ids, 'record_id', binds, int))
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

    #
    # range selects
    #
    if after_timestamp is not None:
        clauses.append("timestamp > :after_ts")
        binds['after_ts'] = after_timestamp
    if before_timestamp is not None:
        clauses.append("timestamp < :before_ts")
        binds['before_timestamp'] = before_timestamp
    if after_id is not None:
        clauses.append("record_id > :after_id")
        binds['after_id'] = int(after_id)
    if before_id is not None:
        clauses.append("record_id < :before_id")
        binds['before_id'] = int(before_id)

    if clauses:
        where = ' WHERE ' + ' AND '.join(clauses)
    else:
        where = ''

    return db.execute(
        query + where,
        binds)


def db_row_to_record(db, row):
    co = Factory.get('Constants')(db)
    row = dict(row)
    row['change_type'] = co.ChangeType(row['change_type'])
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
            params=record.params)

    # def update(self, record):
    #     # TODO: assert DbAuditRecord instance?
    #     data = record.to_dict()
    #     return sql_update(self._db, **data)
