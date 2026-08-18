# -*- coding: utf-8 -*-
#
# Copyright 2005-2026 University of Oslo, Norway
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
Functions to access/modify the entity_trait table.

Common trait selectors
=======================
:func:`.search_traits` and :func:`.delete_traits` use a common set of
arguments/selectors.  These selectors (arguments) are documented in this
*fictional* function:

.. py:function:: select(code=None, entity_id=None, entity_type=None, \
                        target_id=NotSet, \
                        strval=NotSet, strval_like=None, strval_ilike=None, \
                        date=NotSet, date_before=None, date_after=None, \
                        numval=NotSet, numval_min=None, numval_max=None)

   Imaginary selector function to illustrate the common trait lookup arguments.

   :param code: only include these trait types
   :param entity_id: only include these entities
   :param entity_type: only include these entity types

   :param target_id: only include these target entity values

   :param strval: only include these strval values
   :param strval_like: include traits matching this strval pattern
   :param strval_ilike: as strval_like, but case insensitive matching

   :param numval: only include traits with these specific numval values
   :param numval_min: include traits with numval >= numval_min
   :param numval_max: include traits with numval < numval_max

   :param date: only include traits with these date/datetime values
   :param date_after: only include traits with a date value after this
   :param date_before: only include traits with a date value before this

The literal selectors (numval, strval, ...) also apply to :func:`.get_trait`,
for the fields that can be selected in that function.


Selecting fields
-----------------
Fields that take a literal (code, entity_id, entity_type, target_id, strval,
numval, date) can *either* be a:

- A single value
- A sequence (set, tuple, list) - all values are *or*-ed
- But note that sequences *cannot* use ``None`` to mean a literal ``NULL``.
- Fields that take constants support any int-able object


Selecting unset fields
-----------------------
The trait fields (strval, intval, date, target_id) are *optional*.  In lookups,
these arguments are ``NotSet`` by default, and ``select(numval=None)`` will
result in a literal ``numval IS NULL`` lookup.

Note that only these fields can be checked for ``<column> IS NULL``.  ``None``
is not supported in sequences  - there is currently no way to check if e.g.
``(numval IS NULL OR numval = <value>)``


Combining selectors
--------------------
When combining *range*-selectors (i.e. date_before/date_after,
numval_min/numval_max), *both* conditions must be fulfilled.

When combining value selectors and range selectors (e.g. numval and
numval_min/numval_max), the value and range checks are *OR*-ed*.

Example:

``select(numval=(1, 4), numval_min=10, numval_max=40)`` → ``(numval IN (1, 4))
OR (numval >= 10 AND numval < 40)``
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging
import six

import Cerebrum.Errors
from Cerebrum.Utils import NotSet, argument_to_sql
from Cerebrum.database import query_utils
from .constants import CLConstants as TraitChange

__all__ = (
    'DEFAULT_ORDER',
    'DEFAULT_FIELDS',
    'clear_trait',
    'delete_traits',
    'get_trait',
    'search_traits',
    'set_trait',
)


DEFAULT_ORDER = ('entity_id', 'code')
""" Default ordering in searches (:func:`.search_traits`). """

DEFAULT_FIELDS = ('entity_id', 'entity_type', 'code',
                  'target_id', 'date', 'numval', 'strval')
""" Default columns and column ordering for trait rows. """


logger = logging.getLogger(__name__)


def _get_change_params(row_like):
    """
    Get change_params for log_change from a row-like object.

    TODO: Revise change_params:

    - Omit entity_id/entity_type/target_id - these can be inferred from other
      columns (subject/target)
    - We should include the trait code_str - otherwise we have no way of
      telling what the trait *was* in an audit record if the trait type is
      removed
    """
    change_params = dict(row_like)
    date = change_params.get('date')
    if date:
        change_params['date'] = str(date)
    return change_params


def _select(code=None, entity_id=None, entity_type=None,
            target_id=NotSet,
            strval=NotSet, strval_like=None, strval_ilike=None,
            date=NotSet, date_before=None, date_after=None,
            numval=NotSet, numval_min=None, numval_max=None,
            _prefix=''):
    """
    Generate clauses and binds for entity_trait queries.

    See `common trait selectors`_ in the module documentation for more info on
    individual filters/fields.

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

    #
    # mandatory value selects (columns that doesn't allow None)
    #
    if code is not None:
        clauses.append(
            argument_to_sql(code, p + 'code', binds, int))
    if entity_id is not None:
        clauses.append(
            argument_to_sql(entity_id, p + 'entity_id', binds, int))
    if entity_type is not None:
        clauses.append(
            argument_to_sql(entity_type, p + 'entity_type', binds, int))

    #
    # target_id
    #
    if target_id is None:
        clauses.append("({} IS NULL)".format(p + 'target_id'))
    elif target_id is not NotSet:
        clauses.append(argument_to_sql(target_id, p + 'target_id', binds, int))

    #
    # date select
    #
    date_cond, date_binds = query_utils.date_helper(
        colname=p + 'date',
        value=date,
        gt=date_after,
        lt=date_before,
        nullable=True,
    )
    if date_cond:
        clauses.append(date_cond)
    if date_binds:
        binds.update(date_binds)

    #
    # numval selects
    #
    num_conds = []
    if numval is None:
        num_conds.append("({} IS NULL)".format(p + 'numval'))
    elif numval is not NotSet:
        num_conds.append(
            argument_to_sql(numval, p + 'numval', binds, int))

    if numval_min is not None or numval_max is not None:
        n_range = query_utils.NumberRange(ge=numval_min, lt=numval_max)
        n_cond, n_binds = n_range.get_sql_select(p + 'numval', 'numval')
        num_conds.append(n_cond)
        binds.update(n_binds)

    if len(num_conds) > 1:
        clauses.append('({})'.format(' OR '.join(num_conds)))
    elif num_conds:
        clauses.append(num_conds[0])

    #
    # strval selects
    #
    strval_cond, strval_binds = query_utils.pattern_helper(
        colname=p + 'strval',
        value=strval,
        case_pattern=strval_like,
        icase_pattern=strval_ilike,
        nullable=True,
    )
    if strval_cond:
        clauses.append(strval_cond)
    if strval_binds:
        binds.update(strval_binds)

    return clauses, binds


def search_traits(db, limit=None, fetchall=False, **select):
    """
    Search for traits.

    :param int limit:
        limit number of results

    :param bool fetchall:
        - if True, return rows as list
        - if False return rows as iterator

    :param select:
        See `common trait selectors`_ in the module documentation for more info
        on additional search parameters.

    :returns:
        Matching rows
    """
    prefix = 't'
    select_params = {'_prefix': prefix}
    if '_prefix' in select:
        raise TypeError("invalid argument: '_prefix'")
    select_params.update(select)

    conds, binds = _select(**select_params)

    if limit is None:
        limit_clause = ''
    else:
        limit_clause = 'LIMIT :limit'
        binds['limit'] = int(limit)

    stmt = """
      SELECT {cols}
      FROM [:table schema=cerebrum name=entity_trait] t
      {where}
      ORDER BY {order}
      {limit}
    """.format(
        cols=', '.join('{0}.{1} as {1}'.format(prefix, col)
                       for col in DEFAULT_FIELDS),
        where=('WHERE ' + ' AND '.join(conds)) if conds else '',
        order=', '.join('{0}.{1}'.format(prefix, col)
                        for col in DEFAULT_ORDER),
        limit=limit_clause,
    )
    return db.query(stmt, binds, fetchall=fetchall)


def get_trait(db, entity_id, code, target_id=NotSet, date=NotSet,
              numval=NotSet, strval=NotSet):
    """
    Get a specific trait for a given account.

    Also allows additional filters that can be used to check if a given trait
    exists with the given values.  See `common trait selectors`_ in the module
    documentation for these optional filters.

    :returns: A single trait row
    :raises Cerebrum.Errors.NotFoundError: If the row doesn't exist
    """
    select_params = {
        'entity_id': int(entity_id),
        'code': int(code),
        'target_id': target_id,
        'date': date,
        'numval': numval,
        'strval': strval,
    }
    conds, binds = _select(**select_params)

    stmt = """
      SELECT {cols}
      FROM [:table schema=cerebrum name=entity_trait]
      WHERE {conds}
    """.format(
        cols=', '.join(DEFAULT_FIELDS),
        conds=' AND '.join(conds),
    )
    try:
        return db.query_1(stmt, binds)
    except Cerebrum.Errors.NotFoundError:
        return None


def delete_traits(db, **select):
    """
    Delete traits.

    :param select:
        Optional filter parameters to only delete matching traits. See `common
        trait selectors`_ in the module documentation for more info on how to
        select traits to delete.

        .. important::
           If no filter parameters are given, this function will delete *all*
           traits.

    :returns: Deleted rows
    """
    if '_prefix' in select:
        raise TypeError("invalid argument: '_prefix'")
    conds, binds = _select(**select)

    stmt = """
      DELETE FROM [:table schema=cerebrum name=entity_trait]
      {where}
      RETURNING {fields}
    """.format(
        where=('WHERE ' + ' AND '.join(conds)) if conds else '',
        fields=', '.join(DEFAULT_FIELDS),
    )

    deleted_rows = db.query(stmt, binds, fetchall=True)
    for row in deleted_rows:
        logger.info('removed trait code=%r from entity_id=%r',
                    row['code'], row['entity_id'])
        db.log_change(
            subject_entity=row['entity_id'],
            change_type_id=TraitChange.trait_del,
            destination_entity=row['target_id'],
            change_params=_get_change_params(row),
        )
    return deleted_rows


def _insert(db, entity_id, entity_type, code,
            target_id, date, numval, strval):
    binds = {
        'entity_id': int(entity_id),
        'entity_type': int(entity_type),
        'code': int(code),
        'target_id': None if target_id is None else int(target_id),
        'date': date,
        'numval': None if numval is None else int(numval),
        'strval': six.text_type(strval) if strval else None,
    }
    stmt = """
      INSERT INTO [:table schema=cerebrum name=entity_trait]
        ({cols})
      VALUES
        ({binds})
      RETURNING
        {fields}
    """.format(
        cols=', '.join(sorted(binds)),
        binds=', '.join(':' + col for col in sorted(binds)),
        fields=', '.join(DEFAULT_FIELDS),
    )
    row = db.query_1(stmt, binds)
    logger.info('added trait code=%r on entity_id=%r',
                row['code'], row['entity_id'])
    db.log_change(row['entity_id'], TraitChange.trait_add,
                  row['target_id'], change_params=_get_change_params(row))
    return row


def _update(db, entity_id, entity_type, code,
            target_id, date, numval, strval):
    changes = {
        'target_id': None if target_id is None else int(target_id),
        'date': date,
        'numval': None if numval is None else int(numval),
        'strval': six.text_type(strval) if strval else None,
    }
    binds = dict(changes)
    binds.update({
        'entity_id': int(entity_id),
        'entity_type': int(entity_type),
        'code': int(code),
    })

    stmt = """
      UPDATE [:table schema=cerebrum name=entity_trait]
      SET
        {changes}
      WHERE
        entity_id = :entity_id AND code = :code
      RETURNING
        {fields}
    """.format(
        changes=', '.join('{0} = :{0}'.format(col) for col in changes),
        fields=', '.join(DEFAULT_FIELDS),
    )

    row = db.query_1(stmt, binds)
    logger.info('updated trait code=%r on entity_id=%r',
                row['code'], row['entity_id'])
    db.log_change(row['entity_id'], TraitChange.trait_mod,
                  row['target_id'], change_params=_get_change_params(row))
    return row


def set_trait(db, entity_id, entity_type, code,
              target_id=None, date=None, numval=None, strval=None):
    """
    Add or update a trait.

    No partial updates - if a field is not given, it will be cleared.

    :returns: The trait row, with its updated values.
    """
    if not get_trait(db, entity_id, code):
        # no trait <code> for <entity_id> - must insert
        return _insert(db, entity_id, entity_type, code,
                       target_id, date, numval, strval)

    exists = get_trait(db, entity_id, code, target_id=target_id, date=date,
                       numval=numval, strval=strval)
    if exists:
        # identical trait already exists
        return exists
    else:
        # <code> for <entity_id> exists, but with different values
        return _update(db, entity_id, entity_type, code,
                       target_id, date, numval, strval)


def clear_trait(db, entity_id, code):
    """
    Clear a trait

    :returns: The deleted row, or ``None`` if the trait didn't exist.
    """
    rows = list(delete_traits(db, entity_id=int(entity_id), code=int(code)))
    if len(rows) < 1:
        return None

    if len(rows) > 1:
        # Not really possible, unless we've screwed up in this module somewhere
        raise Cerebrum.Errors.TooManyRowsError(
            'delete_trait: multiple code=%r for entity_id=%r'
            % (code, entity_id))

    return rows[0]
