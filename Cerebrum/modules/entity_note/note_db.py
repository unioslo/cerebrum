# -*- coding: utf-8 -*-
#
# Copyright 2013-2026 University of Oslo, Norway
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
Module for attaching notes to entities.


Common note selectors
======================
:func:`.sql_search_notes` and :func:`.sql_delete_notes` use a common set of
arguments/selectors.  These selectors (arguments) are documented in this
*fictional* function:

.. py:function:: select(note_id=None, entity_id=None, creator_id=None, \
                        create_date=None, created_before=None, \
                        created_after=None, subject=NotSet, \
                        subject_like=None, subject_ilike=None, \
                        description=NotSet, description_like=None, \
                        description_ilike=None)

   Imaginary selector function to illustrate the common note lookup arguments.

   :param note_id: only match these note ids
   :param entity_id: only match notes for these entities
   :param creator_id: only match notes created by these account ids

   :param create_date: only match notes created *at* these date/datetimes
   :param created_after: only match notes created after this datetime
   :param created_before: only match notes created before this datetime

   :param subject: only match results for these subject values
   :param subject_like: match notes with this subject pattern
   :param subject_ilike: as subject_like, but case insensitive

   :param description: only match these description values
   :param description_like: match notes with this description pattern
   :param description_ilike: as description_like, but case insensitive

*create_date* is a datetime/timestamp and not a date, despite its name.


Selecting fields
-----------------
Fields that take a literal (note_id, entity_id, creator_id, create_date,
subject, description) can *either* be a:

- A single value
- A sequence (set, tuple, list) - all values are *or*-ed
- But note that sequences *cannot* use ``None`` to mean a literal ``NULL``.


Selecting unset fields
-----------------------
The subject and description fields are *optional*.  In lookups, these arguments
are ``NotSet`` by default, and ``select(subject=None)`` will result in a
``subject IS NULL`` lookup.

Note that only these fields can be checked for ``<column> IS NULL``.  ``None``
is not supported in sequences  - there is currently no way to check if e.g.
``subject IS NULL OR subject = <value>``


Combining selectors
--------------------
When combining the date range selectors (created_before, created_after), *both*
conditions must be fulfilled:

``select(created_before=B, created_after=A)`` → ``(create_date < B AND
create_date > A)``

When combining literal values, patterns, or ranges for a given column (e.g.
subject and subject_ilike, or create_date and created_after), the value, range,
and patterns are *OR*-ed*.

Example:

``select(subject="foo", subject_like="Bar *")`` → ``(subject = "foo" OR subject
LIKE "Bar %")``

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

from .note_constants import NoteChangeCodes as NoteChange
from Cerebrum.Utils import NotSet, argument_to_sql
from Cerebrum.database import query_utils
from Cerebrum.utils import date_compat

__all__ = (
    'DEFAULT_ORDER',
    'DEFAULT_FIELDS',
    'sql_search_notes',
    'sql_add_note',
    'sql_delete_notes',
)


DEFAULT_ORDER = ('entity_id', 'create_date', 'note_id')
""" Default ordering in searches (:func:`.sql_search_notes`). """


DEFAULT_FIELDS = ('note_id', 'entity_id', 'create_date', 'creator_id',
                  'subject', 'description')
""" Default columns and column ordering for note rows. """


logger = logging.getLogger(__name__)


def _select(note_id=None, entity_id=None, creator_id=None,
            create_date=None, created_before=None, created_after=None,
            subject=NotSet, subject_like=None, subject_ilike=None,
            description=NotSet, description_like=None, description_ilike=None,
            _prefix=''):
    """
    Generate clauses and binds for entity_note queries.

    See `common note selectors`_ in the module documentation for more info on
    individual filters/fields.

    :param _prefix:
        A prefix for entity_note column names.

        A prefix is needed when joining multiple tables, and a column in
        entity_note may conflict with column names from another table.

    :rtype: tuple(list, dict)
    :returns:
        Returns a list of conditions, and a dict of query params.
    """
    p = '{}.'.format(_prefix.rstrip('.')) if _prefix else ''
    clauses = []
    binds = {}

    # numeric columns that doesn't allow NULL
    for value, column in (
            (note_id, 'note_id'),
            (entity_id, 'entity_id'),
            (creator_id, 'creator_id')):
        if value is not None:
            clauses.append(
                argument_to_sql(value, p + column, binds, int))

    # create_date select
    #
    # We use get_datetime_tz on after/before to ensure that the types
    # are comparable
    date_cond, date_binds = query_utils.date_helper(
        colname=p + 'create_date',
        value=create_date,
        gt=date_compat.get_datetime_tz(created_after),
        lt=date_compat.get_datetime_tz(created_before),
        nullable=False,
    )
    if date_cond:
        clauses.append(date_cond)
    if date_binds:
        binds.update(date_binds)

    # subject selects
    subj_cond, subj_binds = query_utils.pattern_helper(
        colname=p + 'subject',
        value=subject,
        case_pattern=subject_like,
        icase_pattern=subject_ilike,
        nullable=True,
    )
    if subj_cond:
        clauses.append(subj_cond)
    if subj_binds:
        binds.update(subj_binds)

    # description selects
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

    return clauses, binds


def sql_add_note(db, entity_id, creator_id, subject, description=None):
    """
    Add a note to an entity.

    :type db: Cerebrum.database.Database

    :param int entity_id: entity to add a note to
    :param int creator_id: account that adds the note
    :param str subject: note subject
    :param str description: note body (optional)

    :returns: Returns the newly added note row
    """
    if subject is None or len(subject) > 70:
        raise ValueError("Subject cannot be null, and must be no longer"
                         " than 70 characters.")
    note_id = db.nextval("entity_note_seq")

    row = db.query_1(
        """
        INSERT INTO [:table schema=cerebrum name=entity_note]
          (note_id, entity_id, creator_id, subject, description)
        VALUES
          (:note_id, :entity_id, :creator_id, :subject, :description)
        RETURNING
          {cols}
        """.format(cols=', '.join(DEFAULT_FIELDS)),
        {
            'note_id': int(note_id),
            'entity_id': int(entity_id),
            'creator_id': int(creator_id),
            'subject': subject,
            'description': description,
        })

    logger.debug('added note note_id=%r to entity_id=%r',
                 row['note_id'], row['entity_id'])
    db.log_change(
        subject_entity=int(row['entity_id']),
        change_type_id=NoteChange.entity_note_add,
        destination_entity=None,
        change_params={
            'note_id': int(row['note_id']),
        },
    )

    return row


def sql_search_notes(db, fetchall=True, limit=None, entity_type=None,
                     **search):
    """
    Search for note entries.

    :param fetchall: See ``Cerebrum.database.Database.query``
    :param limit: Limit number of results
    :param entity_type: Only include results for these entity types
    :param search: See `common note selectors`_ in the module documentation.

    :returns: Matching rows.
    """
    select_params = {'_prefix': 'en'}
    if '_prefix' in search:
        raise TypeError('invalid argument: _prefix')
    select_params.update(search)

    clauses, binds = _select(**select_params)

    if entity_type is not None:
        clauses.append(
            argument_to_sql(entity_type, 'et.entity_type', binds, int))

    if limit is None:
        limit_clause = ''
    else:
        limit_clause = 'LIMIT :limit'
        binds['limit'] = int(limit)

    if clauses:
        where = ' WHERE ' + ' AND '.join(clauses)
    else:
        where = ''

    query = """
      SELECT {fields}
      FROM [:table schema=cerebrum name=entity_note] en
      JOIN [:table schema=cerebrum name=entity_info] et
        ON en.entity_id = et.entity_id
      {where}
      ORDER BY {order}
      {limit}
    """.strip().format(
        fields=', '.join('en.' + f for f in DEFAULT_FIELDS),
        where=where,
        order=', '.join('en.' + f for f in DEFAULT_ORDER),
        limit=limit_clause,
    )
    return db.query(query, binds, fetchall=fetchall)


def sql_delete_notes(db, **selects):
    """
    Delete note entries.

    See `common note selectors`_ in the module documentation for more info on
    the *selects*.

    :returns: Deleted rows.
    """
    if "_prefix" in selects:
        raise TypeError("invalid argument: '_prefix'")
    clauses, binds = _select(**selects)
    if clauses:
        where = 'WHERE ' + ' AND '.join(clauses)
    else:
        where = ''

    stmt = """
      DELETE FROM [:table schema=cerebrum name=entity_note]
        {where}
      RETURNING
        {fields}
    """.strip().format(
        where=where,
        fields=', '.join(DEFAULT_FIELDS),
    )

    deleted_rows = db.query(stmt, binds, fetchall=True)
    for row in deleted_rows:
        logger.debug('removed note note_id=%r from entity_id=%r',
                     row['note_id'], row['entity_id'])
        db.log_change(
            subject_entity=int(row['entity_id']),
            change_type_id=NoteChange.entity_note_del,
            destination_entity=None,
            change_params={
                'note_id': int(row['note_id']),
            },
        )
    return deleted_rows
