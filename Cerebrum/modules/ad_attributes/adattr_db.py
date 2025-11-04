# -*- coding: utf-8 -*-
#
# Copyright 2012-2025 University of Oslo, Norway
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
Database access for storing Active Directory (AD) attributes in Cerebrum.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

import six

from Cerebrum import Constants
from Cerebrum import Errors

from Cerebrum.Utils import argument_to_sql
from Cerebrum.database import query_utils

from . import adattr_constants


# Attribute ordering in query results
DEFAULT_ORDER = ("entity_id", "spread_code", "attr_code", "subattr_id")

# Fields and field order in ad_attributes query results
DEFAULT_FIELDS = ("entity_id", "spread_code", "attr_code", "subattr_id",
                  "value")

logger = logging.getLogger(__name__)


def _assert_attribute_code(value):
    """ helper - ensure input argument is an _ADAttrCode """
    if isinstance(value, adattr_constants._ADAttrCode):
        return value
    raise ValueError("invalid ad attribute: " + repr(value))


def _assert_spread_code(value):
    """ helper - ensure input argument is a _SpreadCode """
    if isinstance(value, Constants._SpreadCode):
        return value
    raise ValueError("invalid spread: " + repr(value))


def _assert_collection(value):
    """ ensure value is a collection. """
    if isinstance(value, (list, tuple, set)):
        return value
    elif not value:
        return tuple()
    else:
        return (value,)


def _select(entity_id=None, spread_code=None, attr_code=None, subattr_id=None,
            value=None, value_like=None, value_ilike=None, _prefix=""):
    """
    Format conditions and bindings for ad_attribute queries.

    :param entity_id: only include results for these entities
    :param spread_code: only include results for these spreads
    :param attr_code: only include results for these attributes
    :param subattr_id: only include results for these sub-id values

    :param value: only include results for these values
    :param value_like: include results matching this pattern
    :param value_ilike: as value_like, but case insensitive matching

    :param _prefix:
        Internal use: prefix for ad_attributes column names.

        A prefix is needed when the resulting conditions and binds should be
        joined with other tables, and column names may conflict.

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
    if entity_id is not None:
        clauses.append(
            argument_to_sql(entity_id, p + "entity_id", binds, int))
    if spread_code is not None:
        clauses.append(
            argument_to_sql(spread_code, p + "spread_code", binds, int))
    if attr_code is not None:
        clauses.append(
            argument_to_sql(attr_code, p + "attr_code", binds, int))

    # TODO: Figure out this bit?
    if subattr_id is not None:
        clauses.append(
            argument_to_sql(subattr_id, p + "subattr_id", binds, int))

    #
    # value selects
    #
    value_cond, value_binds = query_utils.pattern_helper(
        colname=p + "value",
        value=value,
        case_pattern=value_like,
        icase_pattern=value_ilike,
        nullable=False,
    )
    if value_cond:
        clauses.append(value_cond)
    if value_binds:
        binds.update(value_binds)

    return clauses, binds


def search_ad_attributes(db, fetchall=True, limit=None, **search):
    """
    Search for attributes.

    :type db: Cerebrum.database.Database
    :param fetchall: See ``Cerebrum.database.Database.query``
    :param int limit: Optionally limit number of results

    See :func:`._select` for available search filters.

    :returns: Matching database rows
    """
    if "_prefix" in search:
        raise TypeError("invalid argument: _prefix")

    clauses, binds = _select(**search)

    if limit is None:
        limit_clause = ""
    else:
        limit_clause = "LIMIT :limit"
        binds['limit'] = int(limit)

    if clauses:
        where = " WHERE " + " AND ".join(clauses)
    else:
        where = ""

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
      FROM [:table schema=cerebrum name=ad_attribute]
      {where}
      ORDER BY {order}
      {limit}
    """.strip().format(
        fields=", ".join(DEFAULT_FIELDS),
        where=where,
        order=", ".join(DEFAULT_ORDER),
        limit=limit_clause,
    )
    return db.query(query, binds, fetchall=fetchall)


def get_ad_attribute(db, entity_id, spread_code, attr_code, subattr_id=None):
    """
    Get attribute value.

    :type db: Cerebrum.database.Database
    :param int entity_id: Object to set the attribute for
    :param _SpreadCode spread_code: Spread where this attribute applies
    :param _ADAttrCode attr_code: One of the pre-defined attributes
    :param int subattr_id: optionally get specific value for multivalued attr

    :returns:
        Either a single row (for single-valued attributes) or a list of
        rows (for multivalued attributes).
    """
    # Make sure input constants are actual constant objects, and not just ints.
    attr_code = _assert_attribute_code(attr_code)

    if subattr_id and not attr_code.multivalued:
        raise ValueError(
            "invalid subattr_id=%s for single-valued attribute %s"
            % (repr(subattr_id), six.text_type(attr_code)))
    multivalue_result = attr_code.multivalued and subattr_id is None

    params = {
        'entity_id': int(entity_id),
        'spread_code': int(spread_code),
        'attr_code': int(attr_code),
    }
    if subattr_id is not None:
        params['subattr_id'] = int(subattr_id)

    rows = list(search_ad_attributes(db, **params))
    if len(rows) == 0:
        raise Errors.NotFoundError("ad attribute %s" % repr(params))

    if multivalue_result:
        return rows

    if len(rows) == 1:
        return rows[0]

    # Single valued attribute, but we found multiple rows?
    raise Errors.TooManyRowsError("ad attribute %s" % repr(params))


def set_ad_attribute(db, entity_id, spread_code, attr_code, subattr_id, value):
    """
    Set an Active Directory attribute for a given entity.

    :type db: Cerebrum.database.Database
    :param int entity_id: Object to set the attribute for
    :param _SpreadCode spread_code: Spread where this attribute applies
    :param _ADAttrCode attr_code: One of the pre-defined attributes
    :param int subattr_id: Index for multivalued attributes
    :param str value: Attribute value

    :returns: The (updated) row
    """
    # Make sure input constants are actual constant objects, and not just ints.
    attr_code = _assert_attribute_code(attr_code)
    spread_code = _assert_spread_code(spread_code)

    # Sanity check - prevent subattr-id for single-valued attributes
    # TODO: Do we even need multivalue-support?
    if int(subattr_id) and not attr_code.multivalued:
        raise ValueError(
            "invalid subattr_id=%s for single-valued attribute %s"
            % (repr(subattr_id), six.text_type(attr_code)))

    fields = DEFAULT_FIELDS
    conds = ["{0} = :{0}".format(f) for f in ("entity_id", "spread_code",
                                              "attr_code", "subattr_id")]
    binds = {
        'entity_id': int(entity_id),
        'spread_code': int(spread_code),
        'attr_code': int(attr_code),
        'subattr_id': int(subattr_id),
    }

    try:
        prev = get_ad_attribute(db, entity_id, spread_code, attr_code,
                                subattr_id=subattr_id)
        if prev['value'] == value:
            return prev
    except Errors.NotFoundError:
        prev = None

    binds.update({
        'value': value,
    })
    if prev:
        row = db.query_1(
            """
            UPDATE [:table schema=cerebrum name=ad_attribute]
            SET value = :value
            WHERE {where}
            RETURNING {fields}
            """.format(
                fields=", ".join(fields),
                where=" AND ".join(conds),
            ),
            binds,
        )
    else:
        row = db.query_1(
            """
            INSERT INTO [:table schema=cerebrum name=ad_attribute] ({fields})
            VALUES ({keys})
            RETURNING {fields}
            """.format(
                fields=", ".join(fields),
                keys=", ".join(":{}".format(f) for f in fields),
            ),
            binds,
        )
    logger.debug("set ad-attribute"
                 " entity-id=%r, attr=%r, spread=%r, sub=%r",
                 row['entity_id'], row['attr_code'], row['spread_code'],
                 row['subattr_id'])
    db.log_change(
        row['entity_id'],
        adattr_constants.AdAttributeChangeConstants.ad_attr_add,
        None,
        change_params={
            'spread': six.text_type(spread_code),
            'attr': six.text_type(attr_code),
            'value': row['value'],
        },
    )
    return row


def delete_ad_attributes(db, **filters):
    """
    Delete matching hard-coded Active Directory attribute values.

    :type db: Cerebrum.database.Database

    .. warning::
       Deletes *all* matching attributes.  Without any all attributes
       will be deleted.  See :func:`._select` for available delete filters.

    :returns: Matching database rows
    """
    if "_prefix" in filters:
        raise TypeError("invalid argument: _prefix")

    # Make reverse lookup for db.log_change().  We *could* fetch an instance of
    # Factory.get("Constants") here and build a lookup from all known codes,
    # but that may get expensive if we do a lot of individual delete calls.
    #
    # Note that this means that `change_params` will only work correctly if we
    # delete *selected* spreads and attributes.  If we e.g. delete *all*
    # attributes for a given account (attr_code=None), the `change_params` will
    # contain the constant int-values.  It's always been this way, but we may
    # want to look into this at some point...
    attrs = {
        int(v): _assert_attribute_code(v)
        for v in _assert_collection(filters.get("attr_code"))
    }
    spreads = {
        int(s): _assert_spread_code(s)
        for s in _assert_collection(filters.get("spread_code"))
    }

    clauses, binds = _select(**filters)
    if clauses:
        where = " WHERE " + " AND ".join(clauses)
    else:
        where = ""

    stmt = """
      DELETE FROM [:table schema=cerebrum name=ad_attribute]
      {where}
      RETURNING {fields}
    """.strip().format(
        fields=", ".join(DEFAULT_FIELDS),
        where=where,
    )
    deleted_rows = db.query(stmt, binds, fetchall=True)
    for row in deleted_rows:
        logger.debug("removed ad-attribute"
                     " entity-id=%s, attr=%r, spread=%r, sub=%r",
                     row['entity_id'], row['attr_code'], row['spread_code'],
                     row['subattr_id'])

        db.log_change(
            row['entity_id'],
            adattr_constants.AdAttributeChangeConstants.ad_attr_del,
            None,
            change_params={
                'spread': six.text_type(spreads.get(row['spread_code'],
                                                    row['spread_code'])),
                'attr': six.text_type(attrs.get(row['attr_code'],
                                                row['attr_code'])),
            },
        )
    return deleted_rows
