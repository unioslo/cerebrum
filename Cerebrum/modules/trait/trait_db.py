# -*- coding: utf-8 -*-
#
# Copyright 2005-2022 University of Oslo, Norway
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
"""
import logging
import six

import Cerebrum.Errors
from Cerebrum.Utils import NotSet, argument_to_sql
from Cerebrum.database.query_utils import NumberRange, Pattern
from .constants import CLConstants as TraitChange


# Task ordering in query results
DEFAULT_ORDER = ('entity_id', 'code')

# Fields and field order in entity_trait query results
DEFAULT_FIELDS = ('entity_id', 'entity_type', 'code',
                  'target_id', 'date', 'numval', 'strval')


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


def _assert_not_none(value):
    if value is None:
        raise ValueError("invalid value: cannot be None")
    return value


def _select(code=None, entity_id=None, entity_type=None,
            target_id=NotSet,
            strval=NotSet, strval_like=None, strval_ilike=None,
            date=NotSet, date_before=None, date_after=None,
            numval=NotSet, numval_min=None, numval_max=None,
            _prefix=''):
    """
    Generate clauses and binds for entity_trait queries.

    >>> _select(numval_min=1, strval=("foo", "bar"), date=None)
    (
        ['(date IS NULL)',
         '(numval >= :numval_start)',
         '(strval IN (:strval1, :strval2))']
        {'numval_start': 1, 'strval1': 'foo', 'strval2': 'bar'},
    )

    A note on selecting unset fields:

     - use `<field>=None` to check if field is unset.
     - only NULL-able fields can be checked for `<column> IS NULL`
     - not supported in sequences  - there is currently no way to check if
       e.g. `(numval IS NONE OR numval = <value>)`

    >>> _select(numval=None)[0]
    ['(numval IS NULL)']

    When combining *range*-selectors (i.e. date_before/date_after,
    numval_min/numval_max), *both* conditions must be fulfilled - i.e. the
    numval in the given row must be *both* smaller than numval_max and larger
    than numval_min:

    >>> _select(numval_min=1, numval_max=4)[0]
    ['(numval >= :numval_start AND numval < :numval_stop)']

    When combining value selectors and range selectors (e.g. numval and
    numval_min/numval_max), the value and range checks are *OR*-ed:

    >>> _select(numval=(1, 4), numval_min=10, numval_max=40)[0]
    [
        '((numval IN (:numval0, :numval1)) OR '
        '(numval >= :numval_start AND numval < :numval_stop))'
    ]


    :param code: only include results for these trait types
    :param entity_id: only include results for these entities
    :param entity_type: only include results for these entity types
    :param target_id: only include results for these target entity values

    :param strval: only include results for these strval values
    :param strval_like: include results matching this strval pattern
    :param strval_ilike: as strval_like, but case insensitive matching

    :param numval: only include results for these specific numval values
    :param numval_min: include results with numval >= numval_min
    :param numval_max: include results with numval < numval_max

    :param date: only include results for these date/datetime values
    :param date_after: only include results with a date value after this
    :param date_before: only include results with a date value before this

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
    date_conds = []

    # None or specific date values
    if date is None:
        date_conds.append("({} IS NULL)".format(p + 'date'))
    elif date is not NotSet:
        date_conds.append(
            argument_to_sql(date, p + 'date', binds, _assert_not_none))

    # range - TODO: Implement date/datetime range util
    if date_before and date_after and date_before < date_after:
        # a date can never be *both* before <t> *and* after that same
        # <t>+<delta>
        raise ValueError("date_after: cannot be after date_before"
                         " (%s < date < %s)" % (date_before, date_after))
    date_range = []
    if date_after:
        date_range.append("{0} > :date_a".format(p + 'date'))
        binds['date_a'] = date_after
    if date_before:
        date_range.append("{0} < :date_b".format(p + 'date'))
        binds['date_b'] = date_before
    if len(date_range) > 1:
        date_conds.append('({})'.format(' AND '.join(date_range)))
    elif date_range:
        date_conds.append(date_range[0])

    if len(date_conds) > 1:
        clauses.append('({})'.format(' OR '.join(date_conds)))
    elif date_conds:
        clauses.append(date_conds[0])

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
        n_range = NumberRange(ge=numval_min, lt=numval_max)
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
    str_conds = []

    # match
    if strval is None:
        str_conds.append("({} IS NULL)".format(p + 'strval'))
    elif strval is not NotSet:
        str_conds.append(
            argument_to_sql(strval, p + 'strval', binds, six.text_type))

    # case-sensitive pattern
    if strval_like:
        sc_pattern = Pattern(strval_like, case_sensitive=True)
        sc_cond, sc_bind = sc_pattern.get_sql_select(p + 'strval', 'c_pattern')
        str_conds.append(sc_cond)
        binds.update(sc_bind)

    # case-insensitive pattern
    if strval_ilike:
        si_pattern = Pattern(strval_ilike, case_sensitive=False)
        si_cond, si_bind = si_pattern.get_sql_select(p + 'strval', 'i_pattern')
        str_conds.append(si_cond)
        binds.update(si_bind)

    if len(str_conds) > 1:
        clauses.append('({})'.format(' OR '.join(str_conds)))
    elif str_conds:
        clauses.append(str_conds[0])

    return clauses, binds


def search_traits(db, limit=None, fetchall=False, **kwargs):
    """
    Search for traits in the entity_trait table.

    See py:func:`._select` for info on selectors/search parameters.

    :param int limit:
        limit number of results

    :param bool fetchall:
        - if True, return rows as list
        - if False return rows as iterator
    """
    prefix = 't'
    select_params = {'_prefix': prefix}
    if '_prefix' in kwargs:
        raise TypeError("invalid argument: '_prefix'")
    select_params.update(kwargs)

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

    Optional filtering to check if a given trait exists with the given values.
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


def delete_traits(db, **selects):
    """
    Delete personal otp secrets.

    See py:func:`._select` for filter params.

    :returns: deleted rows.
    """
    if '_prefix' in selects:
        raise TypeError("invalid argument: '_prefix'")
    conds, binds = _select(**selects)

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

    Note: No partial updates - if a field is not given, it will be cleared.
    """
    if not get_trait(db, entity_id, code):
        # no trait <code> for <entity_id> - must insert
        return _insert(db, entity_id, entity_type, code,
                       target_id, date, numval, strval)

    exists = get_trait(db, entity_id, code, target_id=target_id, date=date,
                       numval=numval, strval=strval)
    if exists:
        # identical trait alreay exists
        return exists
    else:
        # <code> for <entity_id> exists, but with different values
        return _update(db, entity_id, entity_type, code,
                       target_id, date, numval, strval)


def clear_trait(db, entity_id, code):
    """
    Clear a trait.
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
