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
Contact info for entities.

This module contains all entity_contact_info database access and queries.

Notes
------
The contact info table/data model a bit odd:

No update
    Contact info does not support updates.  To modify a contact
    value, you need to first remove the old value, then add a new.

    This oddity is due to the primary key including ``contact_pref``.

``contact_pref``
   The contact info table was designed with support for multiple value entries
   of the same contact ``(entity_id, source_system, contact_type)``.  These
   contacts are separated by a *priority* value.  While supported, it is not
   usually advisable to use this feature.

   This feature is probably to support source systems with multiple values.  In
   practice, we never, or rarely want multiple contacts of the same type, from
   the same source.

   The use of ``contact_pref`` can mostly be avoided by selecting appropriate
   values, and avoid using multi-field values from source systems.

``contact_alias``
    Contacts support an *alternate* value, in the form of a ``contact_alias``
    value.  This value is typically used to add e.g. an *internal dialing
    number* for e.g. an office phone number.

    The use of this alias value can be avoided by simply adding *alternate*
    values of a contact as a separate contact type.

``description``
    Contact info records support adding a description.  This has never been
    used.


TODO
-----
Simplify the contact info data model, by removing:

- ``contact_pref`` (only support one contact from a given source)
- ``contact_alias`` (use a separate contact-type if an alias is needed)
- ``description`` (not really needed, or useful)

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

from Cerebrum.Constants import CLConstants as change_types  # noqa: N813
from Cerebrum.database import query_utils
from Cerebrum.Utils import NotSet
from Cerebrum.Utils import argument_to_sql

logger = logging.getLogger(__name__)

# PRIMARY KEY (entity_id, source_system, contact_type, contact_pref)
DEFAULT_ORDER = ('entity_id', 'contact_type', 'source_system', 'contact_pref')


def _select_cinfo(
        entity_id=None, source_system=None, contact_type=None,
        value=None, value_like=None, value_ilike=None,
        pref=None, pref_min=None, pref_max=None,
        alias=NotSet, alias_like=None, alias_ilike=None,
        description=NotSet, description_like=None, description_ilike=None,
        modified_at=None, modified_after=None, modified_before=None,
        _prefix=''):
    """
    Generate clauses and binds for entity_external_id queries.

    Columns
        All column match fields can either be:

        1. The default value - which means no filter will be applied
        2. A single, exact value to find
        3. A sequence of values (but note that `None` cannot be used in
           sequences)
        4. A single `None` value for nullable fields - i.e. alias, description

    Nullable
        alias and description are nullable fields.  If a `None` value is given,
        we will match columns set to NULL.

    Patterns and ranges
        In columns with multiple filter rules (e.g. pref + pref_min or alias +
        alis_ilike), each column filter will be OR-ed.

    :param entity_id: only include results for these entities
    :param source_system: only include results for these source systems
    :param contact_type: only include results of these types

    :param value: only include results for these values
    :param value_like: include results matching this value pattern
    :param value_ilike: as value_like, but case insensitive

    :param pref: only include results for these preference values
    :param pref_min: include results with a pref >= pref_min
    :param pref_max: include results with a pref <= pref_max

    :param alias: only include results for these aliass
    :param alias_like: include results matching this alias pattern
    :param alias_ilike: as alias_like, but case insensitive

    :param description: only include results for these descriptions
    :param description_like: include results matching this description pattern
    :param description_ilike: as description_like, but case insensitive

    :param modified_at: only include results for these modified values
    :param modified_after: include results with a modified > modified_after
    :param modified_before: include results with a modified < modified_before

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
    if source_system is not None:
        clauses.append(
            argument_to_sql(source_system, p + 'source_system', binds, int))
    if contact_type is not None:
        clauses.append(
            argument_to_sql(contact_type, p + 'contact_type', binds, int))

    #
    # contact_value
    #
    value_cond, value_binds = query_utils.pattern_helper(
        colname=p + 'contact_value',
        value=value,
        case_pattern=value_like,
        icase_pattern=value_ilike,
        nullable=False,
    )
    if value_cond:
        clauses.append(value_cond)
    if value_binds:
        binds.update(value_binds)

    #
    # contact_pref
    #
    pref_cond, pref_binds = query_utils.int_helper(
        colname=p + 'contact_pref',
        value=pref,
        ge=pref_min,
        le=pref_max,
        nullable=False,
    )
    if pref_cond:
        clauses.append(pref_cond)
    if pref_binds:
        binds.update(pref_binds)

    #
    # contact_alias
    #
    alias_cond, alias_binds = query_utils.pattern_helper(
        colname=p + 'contact_alias',
        value=alias,
        case_pattern=alias_like,
        icase_pattern=alias_ilike,
        nullable=True,
    )
    if alias_cond:
        clauses.append(alias_cond)
    if alias_binds:
        binds.update(alias_binds)

    #
    # description
    #
    desc_cond, desc_binds = query_utils.pattern_helper(
        colname=p + 'description',
        value=description,
        case_pattern=description_like,
        icase_pattern=description_ilike,
        nullable=True,
    )
    if desc_cond:
        clauses.append(desc_cond)
    if desc_binds:
        binds.update(desc_binds)

    #
    # last_modified
    #
    mod_cond, mod_binds = query_utils.date_helper(
        colname=p + 'last_modified',
        value=modified_at,
        gt=modified_after,
        lt=modified_before,
        nullable=False,
    )
    if mod_cond:
        clauses.append(mod_cond)
    if mod_binds:
        binds.update(mod_binds)

    return clauses, binds


def search_contact_info(db, limit=None, fetchall=False,
                        entity_type=None, **kwargs):
    """
    Search for contact info in the entity_contact_info table.

    See py:func:`._select_cinfo` for info on selectors/search parameters.

    :param entity_type: only include results for these entity types

    :param int limit:
        limit number of results

    :param bool fetchall:
        - if True, return rows as list
        - if False return rows as iterator
    """
    select_params = {'_prefix': "ci"}
    if '_prefix' in kwargs:
        raise TypeError("invalid argument: '_prefix'")
    select_params.update(kwargs)
    conds, binds = _select_cinfo(**select_params)

    if entity_type is not None:
        conds.append(
            argument_to_sql(entity_type, 'ei.entity_type', binds, int))

    if limit is None:
        limit_clause = ""
    else:
        limit_clause = "LIMIT :limit"
        binds['limit'] = int(limit)

    stmt = """
        SELECT
            ci.entity_id, ci.source_system, ci.contact_type, ci.contact_pref,
            ci.contact_value, ci.contact_alias, ci.description,
            ci.last_modified
        FROM [:table schema=cerebrum name=entity_contact_info] ci
        JOIN [:table schema=cerebrum name=entity_info] ei
          ON ci.entity_id = ei.entity_id
        {where}
        ORDER BY {order}
        {limit}
    """.format(
        where=("WHERE " + " AND ".join(conds)) if conds else "",
        order=", ".join("ci.{}".format(col) for col in DEFAULT_ORDER),
        limit=limit_clause,
    )
    return db.query(stmt, binds, fetchall=fetchall)


def delete_contact_info(db, **selects):
    """
    Delete contact info from the entity_contact_info table.

    See py:func:`._select_cinfo` for info on selectors/search parameters.
    """
    if '_prefix' in selects:
        raise TypeError("invalid argument: '_prefix'")
    conds, binds = _select_cinfo(**selects)

    stmt = """
        DELETE FROM
        [:table schema=cerebrum name=entity_contact_info]
        {where}
        RETURNING
            entity_id, source_system, contact_type, contact_pref,
            contact_value, contact_alias, description,
            last_modified
    """.format(
        where=("WHERE " + " AND ".join(conds)) if conds else "",
    )
    change_type = change_types(db).entity_cinfo_del
    deleted_rows = db.query(stmt, binds, fetchall=True)
    for row in deleted_rows:
        logger.info('removed contact source=%r type=%r from entity_id=%r',
                    row['source_system'], row['contact_type'],
                    row['entity_id'])
        db.log_change(
            row['entity_id'],
            change_type,
            None,
            change_params={
                'type': row['contact_type'],
                'src': row['source_system'],
            },
        )
    return deleted_rows


def add_contact_info(db, entity_id, source_system, contact_type, contact_pref,
                     contact_value, description, contact_alias,
                     _last_modified=None):
    """
    Insert a new contact info row.
    """
    row = db.query_1(
        """
          INSERT INTO [:table schema=cerebrum name=entity_contact_info]
            (entity_id, source_system, contact_type, contact_pref,
             contact_value, description, contact_alias, last_modified)
          VALUES
            (:entity_id, :source_system, :contact_type, :contact_pref,
             :contact_value, :description, :contact_alias, :last_modified)
          RETURNING
            entity_id, source_system, contact_type, contact_pref,
            contact_value, description, contact_alias, last_modified
        """,
        {
            'entity_id': int(entity_id),
            'source_system': int(source_system),
            'contact_type': int(contact_type),
            'contact_pref': contact_pref,
            'contact_value': contact_value,
            'description': description,
            'contact_alias': contact_alias,
            'last_modified': _last_modified or '[:now]',
        },
    )
    change_type = change_types(db).entity_cinfo_add
    logger.info('added contact source=%r type=%r to entity_id=%r',
                row['source_system'], row['contact_type'],
                row['entity_id'])
    db.log_change(
        row['entity_id'],
        change_type,
        None,
        change_params={
            'type': row['contact_type'],
            'value': row['contact_value'],
            'src': row['source_system'],
        },
    )
    return row


_DEFAULT_PREF = 1


def set_contact(db, entity_id, source_system, contact_type, contact_value,
                description=None, contact_alias=None):
    """
    Set a contact info value.

    This is a simplified contact info setter - it ignores contact_pref and
    treats the contact info table as a key-value store, where:

    - the key is the tuple (entity_id, source_system, contact_type)
    - the value is the tuple (contact_value, description, contact_alias)

    When called, this function will do one of the following:

    Keep value
        Keep the existing *value* if it exists in the database under the given
        *key*, but remove any duplicates with other (or the same) *value*.

    Update the value
        If one or more entries exist, all with a different *value*, we'll
        delete them all, and insert the new value.

    Insert the value
        If no contacts with the given *key* exists, we simply insert the value.
    """
    exists = search_contact_info(db, entity_id=int(entity_id),
                                 source_system=int(source_system),
                                 contact_type=int(contact_type), fetchall=True)

    to_set = (contact_value, description, contact_alias)
    values = [
        (r['contact_value'], r['description'], r['contact_alias'],
         r['contact_pref']) for r in exists
    ]
    matching_prefs = [v[3] for v in values if v[:3] == to_set]

    if matching_prefs:
        # No-op - we already have our to_set value
        # Let's clean up duplicates and return our matching row
        keep = sorted(matching_prefs)[0]
        duplicates = []
        for v in values:
            if v[3] == keep:
                # Keep this singular value
                continue
            duplicates.extend(
                delete_contact_info(db, entity_id=int(entity_id),
                                    source_system=int(source_system),
                                    contact_type=int(contact_type),
                                    pref=int(v[3]))
            )
        if duplicates:
            logger.info("set_contact() removed %d duplicates",
                        len(duplicates))

        for r in exists:
            if (to_set == (r['contact_value'], r['description'],
                           r['contact_alias'])
                    and keep == r['contact_pref']):
                return r
        raise RuntimeError("This shouldn't happen!")

    if exists:
        old = delete_contact_info(db, entity_id=int(entity_id),
                                  source_system=int(source_system),
                                  contact_type=int(contact_type))
        if old:
            logger.info("set_contact() removed %d old values", len(old))

    return add_contact_info(db, int(entity_id), source_system, contact_type,
                            _DEFAULT_PREF, contact_value, description,
                            contact_alias)
