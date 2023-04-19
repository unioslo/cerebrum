# -*- coding: utf-8 -*-
# Copyright 2013-2023 University of Oslo, Norway
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

TODO
-----

- Move everything related to this module into ``Cerebrum.modules.note``
  sub-modules.  This includes changelog-constants, bofhd-commands, and this
  module.

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

from Cerebrum.Constants import CLConstants as NoteChange
from Cerebrum.Entity import Entity
from Cerebrum.Utils import NotSet, argument_to_sql
from Cerebrum.database import query_utils
from Cerebrum.utils import date_compat

__version__ = "1.2"

# Task ordering in query results
DEFAULT_ORDER = ('entity_id', 'create_date', 'note_id')

DEFAULT_FIELDS = ('note_id', 'entity_id', 'create_date', 'creator_id',
                  'subject', 'description')

logger = logging.getLogger(__name__)


def _select(note_id=None, entity_id=None, creator_id=None,
            create_date=None, created_before=None, created_after=None,
            subject=NotSet, subject_like=None, subject_ilike=None,
            description=NotSet, description_like=None, description_ilike=None,
            _prefix=''):
    """
    Generate clauses and binds for entity_note queries.

    *create_date* is a datetime/timestamp and not a date, despite its name.

    When combining *create_date* with *created_before*/*created_after*,
    the value and and range checks are *OR*-ed (i.e. create_date must be one of
    the given values or be in the given range).  *created_before* and
    *created_after* must both be fulfilled.

    *subject* and *description* are nullable columns, which means that a
    ``None``-value will look for notes where these columns are set to
    ``NULL``.

    :param note_id: only match these note ids
    :param entity_id: only match these entities
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
    Add a note to a given entity.

    :type db: Cerebrum.database.Database
    :param int entity_id: entity to add a note to
    :param int creator_id: account that adds the note
    :param str subject: note subject
    :param str description: note body (optional)

    :returns:
        Returns the newly added note row
    """
    # TODO: Validate subject? Is CHAR(70), and should not be empty
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
    Search for entity note entries.

    :param fetchall: see ``Cerebrum.database.Database.query``
    :param limit: limit number of results
    :param entity_type: only include results for these entity types
    :param search: see :func:`._select` for more search params

    :returns: matching rows.
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
    Delete entity note entries.

    See :func:`._select` for filter params.

    :returns: deleted rows.
    """
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


class EntityNote(Entity):
    """
    Mixin class for adding note support to entity.
    """

    def add_note(self, operator, subject, description=None):
        """
        Adds a note to this entity.

        :param int operator: account id of operator adding the note.
        :param str subject: note subject (header), < 70 chars
        :param str description: note description (body)

        :returns int: the note id of the new note
        """
        note = sql_add_note(
            db=self._db,
            entity_id=self.entity_id,
            creator_id=operator,
            subject=subject,
            description=description,
        )
        return note['note_id']

    def get_notes(self):
        """
        Returns all notes associated with this entity.

        :returns: A sequence of note rows
        """
        return sql_search_notes(
            db=self._db,
            fetchall=True,
            entity_id=int(self.entity_id))

    def delete_note(self, note_id):
        """
        Deletes a note.

        .. note::
           The note-id must be associated with this entity.  If it's associated
           with another entity, nothing happens.

        :param int note_id: id of note to remove
        """
        sql_delete_notes(
            db=self._db,
            entity_id=int(self.entity_id),
            note_id=int(note_id))

    def delete(self):
        """
        Delete this entity and all notes associated with this entity.

        .. note::
           This entity may be a *note creator* for notes associated with
           *other* entities.  These notes will not be deleted - and constraints
           prevent us from deleting this entity.
        """
        sql_delete_notes(
            db=self._db,
            entity_id=int(self.entity_id))
        super(EntityNote, self).delete()
