# -*- coding: utf-8 -*-
#
# Copyright 2002-2026 University of Oslo, Norway
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
External ID for entities.

This module contains all entity_external_id database access and queries.
External IDs are identifiers that are (mainly) used to cross-reference entities
in Cerebrum with other systems.

.. important::
   While the value column is called `external_id` in the `entity_external_id`
   table, it is referred to as `id_value` in function parameters and results
   (row objects).

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging
import six

from Cerebrum.Constants import CLConstants as change_types  # noqa: N813
from Cerebrum.database import query_utils
from Cerebrum.Utils import argument_to_sql
from Cerebrum.utils.mappings import Mapping  # collections[.abc].Mapping

logger = logging.getLogger(__name__)


DEFAULT_ORDER = ('entity_id', 'id_type', 'source_system')


def _select_extid(entity_id=None, entity_type=None,
                  source_system=None, id_type=None,
                  id_value=None, id_value_like=None, id_value_ilike=None,
                  _prefix=''):
    """
    Generate clauses and binds for entity_external_id queries.

    :param entity_id: only include results for these entities
    :param entity_type: only include results for these entity types
    :param source_system: only include results for these source systems
    :param id_type: only include results of these id types

    :param id_value: only include results for these external id values
    :param id_value_like: include results matching this id value pattern
    :param id_value_ilike: as id_value_like, but case insensitive matching

    :param _prefix:
        A prefix for entity_trait column names.

        A prefix is needed when querying multiple tables, and a column in
        entity_trait may conflict with column names from another table.

    :rtype: tuple(list, dict)
    :returns:
        Returns a list of conditions, and a dict of query params.
    """
    p = '{}.'.format(_prefix.rstrip('.')) if _prefix else ''
    clauses = []
    binds = {}

    if entity_id is not None:
        clauses.append(
            argument_to_sql(entity_id, p + 'entity_id', binds, int))
    if entity_type is not None:
        clauses.append(
            argument_to_sql(entity_type, p + 'entity_type', binds, int))
    if source_system is not None:
        clauses.append(
            argument_to_sql(source_system, p + 'source_system', binds, int))
    if id_type is not None:
        clauses.append(
            argument_to_sql(id_type, p + 'id_type', binds, int))

    strval_cond, strval_binds = query_utils.pattern_helper(
        colname=p + 'external_id',
        value=id_value,
        case_pattern=id_value_like,
        icase_pattern=id_value_ilike,
        nullable=False,
    )
    if strval_cond:
        clauses.append(strval_cond)
    if strval_binds:
        binds.update(strval_binds)

    return clauses, binds


def search_external_ids(db, limit=None, fetchall=False, _legacy_name=False,
                        **kwargs):
    """
    Search for external ids in the entity_external_id table.

    See py:func:`._select_extid` for info on selectors/search parameters.

    :param int limit:
        limit number of results

    :param bool fetchall:
        - if True, return rows as list
        - if False return rows as iterator
    """
    select_params = {'_prefix': "id"}
    if '_prefix' in kwargs:
        raise TypeError("invalid argument: '_prefix'")
    select_params.update(kwargs)
    conds, binds = _select_extid(**select_params)
    if limit is None:
        limit_clause = ""
    else:
        limit_clause = "LIMIT :limit"
        binds['limit'] = int(limit)

    stmt = """
        SELECT
            id.entity_id, id.entity_type, id.source_system,
            id.id_type, {value_name}
        FROM
            [:table schema=cerebrum name=entity_external_id] id
        {where}
        ORDER BY {order}
        {limit}
    """.format(
        value_name="id.external_id" + ("" if _legacy_name else " as id_value"),
        where=("WHERE " + " AND ".join(conds)) if conds else "",
        order=", ".join("id.{}".format(col) for col in DEFAULT_ORDER),
        limit=limit_clause,
    )
    return db.query(stmt, binds, fetchall=fetchall)


def delete_external_ids(db, **selects):
    """
    Delete external ids from the entity_external_id table.

    See py:func:`._select_extid` for filter params.  You'll always want to add
    filters for this function (usually *at least* an entity_id).
    """
    if '_prefix' in selects:
        raise TypeError("invalid argument: '_prefix'")
    conds, binds = _select_extid(**selects)

    stmt = """
        DELETE FROM
            [:table schema=cerebrum name=entity_external_id]
        {where}
        RETURNING
            entity_id, entity_type, source_system,
            id_type, external_id as id_value
    """.format(
        where=("WHERE " + " AND ".join(conds) if conds else ""),
    )
    change_type = change_types(db).entity_ext_id_del
    deleted_rows = db.query(stmt, binds, fetchall=True)
    for row in deleted_rows:
        logger.info('removed external id source=%r type=%r from entity_id=%r',
                    row['source_system'], row['id_type'], row['entity_id'])
        db.log_change(
            row['entity_id'],
            change_type,
            None,
            change_params={
                'id_type': row['id_type'],
                'src': row['source_system'],
            },
        )
    return deleted_rows


def _insert_external_id(db, entity_id, entity_type, source_system,
                        id_type, id_value):
    if not id_value:
        raise ValueError("Missing id_value: " + repr(id_value))
    binds = {
        'entity_id': int(entity_id),
        'entity_type': int(entity_type),
        'source_system': int(source_system),
        'id_type': int(id_type),
        'id_value': id_value,
    }
    stmt = """
        INSERT INTO [:table schema=cerebrum name=entity_external_id]
            (entity_id, entity_type, source_system, id_type, external_id)
        VALUES
            (:entity_id, :entity_type, :source_system, :id_type, :id_value)
        RETURNING
            entity_id, entity_type, source_system,
            id_type, external_id as id_value
    """
    change_type = change_types(db).entity_ext_id_add
    row = db.query_1(stmt, binds)
    logger.info('addded external id source=%r type=%r to entity_id=%r',
                row['source_system'], row['id_type'], row['entity_id'])
    db.log_change(
        row['entity_id'],
        change_type,
        None,
        change_params={
            'id_type': row['id_type'],
            'src': row['source_system'],
            'value': row['id_value'],
        },
    )
    return row


def _update_external_id(db, entity_id, source_system, id_type, id_value):
    if not id_value:
        raise ValueError("Missing id_value: " + repr(id_value))
    binds = {
        'entity_id': int(entity_id),
        'source_system': int(source_system),
        'id_type': int(id_type),
        'id_value': id_value,
    }
    stmt = """
        UPDATE
            [:table schema=cerebrum name=entity_external_id]
        SET
            external_id=:id_value
        WHERE
            entity_id=:entity_id
            AND id_type=:id_type
            AND source_system=:source_system
        RETURNING
            entity_id, entity_type, source_system,
            id_type, external_id as id_value
    """
    change_type = change_types(db).entity_ext_id_mod
    row = db.query_1(stmt, binds)
    logger.info('updated external id source=%r type=%r for entity_id=%r',
                row['source_system'], row['id_type'], row['entity_id'])
    db.log_change(
        row['entity_id'],
        change_type,
        None,
        change_params={
            'id_type': row['id_type'],
            'src': row['source_system'],
            'value': row['id_value'],
        },
    )
    return row


def set_external_id(db, entity_id, entity_type, source_system,
                    id_type, id_value):
    """
    Set an external id

    :param int entity_id: the entity to set an external id for
    :param int entity_type: the entity type of the entity_id
    :param int source_system: the source system for this external id
    :param int id_type: the external id type to set
    :param int id_value: the external id value to set
    """
    rows = search_external_ids(db, entity_id=int(entity_id),
                               source_system=int(source_system),
                               id_type=int(id_type), fetchall=True)
    exists = rows[0] if rows else None

    if exists and exists['id_value'] == id_value:
        return exists

    if exists:
        return _update_external_id(db, entity_id, source_system, id_type,
                                   id_value)
    else:
        return _insert_external_id(db, entity_id, entity_type, source_system,
                                   id_type, id_value)


def get_entity_from_ids(db, identifier, *identifiers):
    """
    Find one entity that matches the provided ids.

    :param identifier:
        A single search identifier.  The value must be:

        - a tuple (<id-type>, <id-value>, [source-system])
        - a dict with keys 'id_type', 'id_value', and 'source_system'
          (optional). The meaning of each element in ids matches the tuple
          variant.
    """
    # normalize identifiers to tuples:
    #   (<id-type>, <id-value>, <source-system> or None)
    search_tuples = []
    for p in (identifier,) + identifiers:
        if isinstance(p, Mapping):
            id_type = p['id_type']
            # support external_id for legacy support
            id_value = p.get('id_value', p.get('external_id'))
            source_system = p.get('source_system')
        elif len(p) == 2:
            id_type, id_value = p
            source_system = None
        elif len(p) == 3:
            id_type, id_value, source_system = p
        else:
            raise ValueError("Invalid search params: " + repr(p))
        search_tuples.append((
            int(id_type),
            six.text_type(id_value or ""),
            None if source_system is None else int(source_system),
        ))

    criterias = []
    binds = {}
    for i, params in enumerate(search_tuples):
        id_type, id_value, source_system = params
        pno = six.text_type(i)
        tmpclause = [
            "id_type = :id_type" + six.text_type(pno),
            "external_id = :id_value" + six.text_type(pno),
        ]
        binds.update({
            'id_type' + pno: int(id_type),
            'id_value' + pno: six.text_type(id_value),
        })
        if source_system:
            tmpclause.append("source_system = :source_system" + pno)
            binds['source_system' + pno] = int(source_system)
        criterias.append("(" + " AND ".join(tmpclause) + ")")

    where = " OR ".join(criterias)
    query = """
        SELECT DISTINCT entity_id
        FROM [:table schema=cerebrum name=entity_external_id]
        WHERE {where}
    """.format(where=where)
    return db.query_1(query, binds)


def list_duplicate_ids(db, id_type=None, id_value=None,
                       limit=None, fetchall=False):
    """
    List entities that share a given id-type/id-value combination.

    These entities are usually duplicates, meaning only one entity should
    exist.

    :param id_type:
        Limit matching to ids of these id types.

        Either a single EntityExternalId code, or a sequence of codes.  This is
        a common use case - e.g. look for duplicate NO_BIRTHNO values.

    :param id_value:
        Limit matching to ids with this value.

        Either a string value, or a sequence of string values.  This only makes
        sense if you're looking for issues with a given id value.
    """
    query = """
        SELECT DISTINCT
            a.entity_id, a.entity_type, a.source_system,
            a.id_type, a.external_id as id_value
        FROM
            [:table schema=cerebrum name=entity_external_id] a,
            [:table schema=cerebrum name=entity_external_id] b
        WHERE
            a.entity_id != b.entity_id
            AND a.entity_type = b.entity_type
            AND a.id_type = b.id_type
            AND a.external_id = b.external_id
            {conds}
        ORDER BY {order}
        {limit}
    """
    conds, binds = _select_extid(
        id_type=id_type,
        id_value=id_value,
        _prefix="a",
    )
    if limit is None:
        limit_clause = ''
    else:
        limit_clause = 'LIMIT :limit'
        binds['limit'] = int(limit)
    stmt = query.format(
        conds=("AND " + " AND ".join(conds)) if conds else "",
        order=", ".join("a.{}".format(col) for col in DEFAULT_ORDER),
        limit=limit_clause,
    )
    return db.query(stmt, binds, fetchall=fetchall)


def list_differing_ids(db, entity_id=None, id_type=None,
                       limit=None, fetchall=False):
    """
    List entities with multiple id-values for a given id-type.

    One of these values are usually incorrect, and should be fixed in the
    source system

    :param entity_id:
        Limit matching to ids from these entities.

        Either an int, or a sequence of ints.

    :param id_type:
        Limit matching to ids of these id types.

        Either a single EntityExternalId code, or a sequence of codes.
    """
    query = """
        SELECT DISTINCT
            a.entity_id, a.entity_type, a.source_system,
            a.id_type, a.external_id as id_value
        FROM
            [:table schema=cerebrum name=entity_external_id] a,
            [:table schema=cerebrum name=entity_external_id] b
        WHERE
            a.entity_id = b.entity_id
            AND a.entity_type = b.entity_type
            AND a.id_type = b.id_type
            AND a.external_id != b.external_id
            {conds}
        ORDER BY {order}
        {limit}
    """
    conds, binds = _select_extid(
        entity_id=entity_id,
        id_type=id_type,
        _prefix="a",
    )
    if limit is None:
        limit_clause = ''
    else:
        limit_clause = 'LIMIT :limit'
        binds['limit'] = int(limit)

    stmt = query.format(
        conds=("AND " + " AND ".join(conds)) if conds else "",
        order=", ".join("a.{}".format(col) for col in DEFAULT_ORDER),
        limit=limit_clause,
    )
    return db.query(stmt, binds, fetchall=fetchall)
