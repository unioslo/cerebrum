# -*- coding: utf-8 -*-
#
# Copyright 2020-2024 University of Oslo, Norway
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
Database access to the *ou_structure* table.

This module implements organizational tree database access functions.  Nothing
outside this module should query the *ou_structure* table directly.


Configuration
-------------
``cereconf.DEFAULT_OU_PERSPECTIVE``
    This setting sets the default perspective returned by
    :func:`.get_default_perspective`.


TODO
----
Move all *ou_structure* related queries and statements here.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

import cereconf

import Cerebrum.Errors
from Cerebrum.Constants import CLConstants as PerspectiveChange

logger = logging.getLogger(__name__)


def get_default_perspective(const):
    """ Get the default perspective (org tree) from config.  """
    return const.get_constant(const.OUPerspective,
                              cereconf.DEFAULT_OU_PERSPECTIVE)


def get_parent_id(db, perspective, ou_id):
    """
    Get the parent *ou_id* for a given *ou_id*.

    :param int ou_id: the org unit to look up parent for
    :param int perspective: the perspective (org tree) to use

    :returns int: the parent org unit id (ou_id)
    :raises Cerebrum.Errors.NotFoundError:
        If the given org unit doesn't exist, or if no parent org unit exists
    """
    return db.query_1(
        """
          SELECT parent_id
          FROM [:table schema=cerebrum name=ou_structure]
          WHERE ou_id=:ou_id
            AND perspective=:perspective
        """,
        {
            'ou_id': int(ou_id),
            'perspective': int(perspective),
        },
    )


def get_parent_map(db, perspective):
    """
    Get parent mapping for all org units according to *perspective*.

    :param int perspective: the perspective (org tree) to use

    :returns dict:
        A mapping of *ou_id* -> parent *ou_id* for all org units in the given
        perspective.
    """
    rows = db.query(
        """
          SELECT ou_id, parent_id
          FROM [:table schema=cerebrum name=ou_structure]
          WHERE perspective=:perspective
        """,
        {'perspective': int(perspective)},
    )
    return {r['ou_id']: r['parent_id'] for r in rows}


def list_roots(db, perspective):
    """
    Get all root org units according to *perspective*.

    :param int perspective: the perspective (org tree) to use

    :returns set:
        a set of *ou_id* values for parent-less org units.
    """
    stmt = """
      SELECT ou_id
      FROM [:table schema=cerebrum name=ou_structure]
      WHERE parent_id IS NULL
        AND perspective = :perspective
    """
    return set(int(r['ou_id'])
               for r in db.query(stmt, {'perspective': int(perspective)}))


#
# OU tree update statements
#


def clear_parent(db, perspective, ou_id):
    """
    Remove existing ou parent relationship.

    This will effectively remove the *ou_id* from the org tree perspective.  If
    another org unit has this org unit as its parent, you'll need to clear that
    relationship *first* (all parent relationships *must* ultimately point to a
    root node that has *parent_id* set to None).

    Take care not to break the org tree.  This function should really only be
    called from an automated org unit import.

    :param db:
    :param perspective: org tree to remove relationship from
    :param ou_id: ou id to clear parent relationship from

    :returns:
        The deleted row (as a dict), or *None* if it didn't exist.
    """
    binds = {
        'ou_id': int(ou_id),
        'perspective': int(perspective),
    }
    delete_stmt = """
      DELETE FROM [:table schema=cerebrum name=ou_structure]
      WHERE ou_id=:ou_id
        AND perspective=:perspective
      RETURNING
        ou_id, perspective, parent_id
    """
    try:
        row = db.query_1(delete_stmt, binds)
    except Cerebrum.Errors.NotFoundError:
        return

    logger.info("cleared parent for ou_id=%s "
                "(perspective=%s, old parent_id=%s)",
                row['ou_id'], row['perspective'], row['parent_id'])
    db.log_change(
        row['ou_id'],
        PerspectiveChange.ou_unset_parent,
        None,
        change_params={
            'perspective': int(row['perspective']),
        },
    )
    return dict(row)


def set_parent(db, perspective, ou_id, parent_id):
    """
    Set a *parent_id* value for *ou_id* in *perspective*.

    This will either add a new parent relationship (i.e. add a org unit to the
    org tree), or update an existing parent relationship (i.e. move org unit
    within the org tree).

    Take care to not create cycles in the *perspective* org tree.  This should
    really only be called from an automated org unit import.

    :param db:
    :param perspective: org tree to remove relationship from
    :param ou_id: ou id to clear parent relationship from

    :returns:
        The old row (as a dict) if *ou_id* was already present in the
        perspective, or *None* if it wasn't.
    """
    select_stmt = """
      SELECT ou_id, perspective, parent_id
      FROM [:table schema=cerebrum name=ou_structure]
      WHERE ou_id=:ou_id
        AND perspective=:perspective
    """
    insert_stmt = """
      INSERT INTO [:table schema=cerebrum name=ou_structure]
        (ou_id, perspective, parent_id)
      VALUES
        (:ou_id, :perspective, :parent_id)
      RETURNING
        ou_id, perspective, parent_id
    """
    update_stmt = """
      UPDATE [:table schema=cerebrum name=ou_structure]
      SET parent_id=:parent_id
      WHERE ou_id=:ou_id
        AND perspective=:perspective
      RETURNING
        ou_id, perspective, parent_id
    """
    binds = {
        'ou_id': int(ou_id),
        'perspective': int(perspective),
        'parent_id': None if parent_id is None else int(parent_id),
    }
    try:
        old_row = dict(db.query_1(select_stmt, binds))
    except Cerebrum.Errors.NotFoundError:
        old_row = None

    if old_row and old_row == binds:
        # Record exists and matches - nothing to update
        return old_row

    if old_row:
        new_row = db.query_1(update_stmt, binds)
    else:
        new_row = db.query_1(insert_stmt, binds)

    logger.info("set parent for ou_id=%s "
                "(perspective=%s, old parent_id=%s, new parent_id=%s)",
                new_row['ou_id'], new_row['perspective'],
                old_row['parent_id'] if old_row else None,
                new_row['parent_id'])
    db.log_change(
        new_row['ou_id'],
        PerspectiveChange.ou_set_parent,
        new_row['parent_id'],
        change_params={
            'perspective': int(new_row['perspective']),
        },
    )
    return old_row


#
# Recursive parent/child queries
#

# Template query for `get_recursive_ou_cte()` with cycle protection
_recursive_ou_query_fmt = """
  WITH RECURSIVE ou_tree_search(ou_id, parent_id, distance, perspective) AS (
    SELECT
      init.ou_id,
      init.parent_id,
      1 as distance,
      init.perspective
    FROM [:table schema=cerebrum name=ou_structure] init
    WHERE
      init.{initial_ou_column} = :{bind_ou}
      AND init.perspective = :{bind_perspective}

    UNION ALL

    SELECT
      next.ou_id,
      next.parent_id,
      cur.distance + 1,
      next.perspective
    FROM
      [:table schema=cerebrum name=ou_structure] next,
      ou_tree_search cur
    WHERE
      {next_ou_join_on}
      AND {next_ou_exists}
      AND next.perspective = cur.perspective
  ) CYCLE {initial_ou_column} SET is_cycle USING path
"""

# Cosntants for selecting direction (parent/child) in
# `get_recursive_ou_cte()`
DIRECTION_PARENTS = 0
DIRECTION_CHILDREN = 1

# Parameters for _recursive_ou_query_fmt to decide direction.
_recursion_params = {
    DIRECTION_PARENTS: {
        'initial_ou_column': 'ou_id',
        'next_ou_exists': 'cur.parent_id is not NULL',
        'next_ou_join_on': 'next.ou_id = cur.parent_id',
    },
    DIRECTION_CHILDREN: {
        'initial_ou_column': 'parent_id',
        'next_ou_exists': 'next.parent_id is not NULL',
        'next_ou_join_on': 'next.parent_id = cur.ou_id',
    },
}


def get_recursive_ou_cte(
        direction=DIRECTION_CHILDREN,
        bind_ou='ou_id',
        bind_perspective='perspective'):
    """
    Get a recursive ou tree query.

    The resulting query contains a common table expression (CTE) named
    *ou_tree_search*, which can be used much like a regular table.  When used
    in a query, it needs two extra binds to be provided:

    - <bind_ou>: the initial ou to start the search at
    - <bind_perspective>: the ou_perspective to use in recursion

    :param int parents:
        0 - find parents, 1 - find children

    :param str bind_ou:
        Name of the initial ou binding - default: ou_id

    :param str bind_perspective:
        Name of the ou perspective binding - default: perspective

    :returns str:
        Returns a ou tree CTE for use in other queries.
    """
    params = dict(_recursion_params[direction])
    params.update({
        'bind_ou': bind_ou,
        'bind_perspective': bind_perspective,
    })
    return _recursive_ou_query_fmt.format(**params)


def find_children(db, perspective, ou_id, depth=None):
    """
    Recursively list all children of a given org unit.

    To get all children, grandchildren, etc... of *ou_id*:
    ::

        set(r['ou_id'] for r in find_children(db, perspective, ou_id))

    :param db:
    :param perspective: perspective for the search
    :param ou_id: starting ou (root) for the search
    :param depth: limit recursion depth

    :returns:
        Rows of org unit ids (parent_id, ou_id, distance).

        *ou_id*
            An immediate child of *parent_id* from the same row, and a child or
            grandchild of the initial *ou_id* argument.

        *distance*
            Number of hops from the initial *ou_id* argument to this *ou_id*.

        *parent_id*
            The immediate parent of *ou_id* from the same row.
    """
    conds = []
    binds = {
        'ou_id': int(ou_id),
        'perspective': int(perspective),
    }
    if depth:
        conds.append("distance <= :max_distance")
        binds['max_distance'] = int(depth)

    stmt = """
      {cte}
      SELECT ou_id, distance, parent_id
      FROM ou_tree_search
      {where}
      ORDER BY distance, parent_id, ou_id
    """.format(
        cte=get_recursive_ou_cte(direction=DIRECTION_CHILDREN),
        where=("WHERE " + " AND ".join(conds)) if conds else "",
    )
    return db.query(stmt, binds)


def find_parents(db, perspective, ou_id, depth=None):
    """
    Recursively list all parents of a given org unit.

    To get a set of all parents of *ou_id*:
    ::

        set(r['parent_id'] for r in find_parents(db, perspective, ou_id))

    :param db:
    :param perspective: perspective for the search
    :param ou_id: starting ou (leaf) for the search
    :param depth: limit recursion depth

    :returns:
        Rows of parent org unit ids (ou_id, parent_id, distance).

        *parent_id*
            The parent of *ou_id* from the same row.

        *ou_id*
            The immediate child that this *parent_id* is a parent for.

        *distance*
            Number of hops from the initial *ou_id* argument to this
            *parent_id*.
    """
    conds = ["parent_id IS NOT NULL"]
    binds = {
        'ou_id': int(ou_id),
        'perspective': int(perspective),
    }
    if depth:
        conds.append("distance <= :max_distance")
        binds['max_distance'] = int(depth)

    stmt = """
      {cte}
      SELECT parent_id, distance, ou_id
      FROM ou_tree_search
      WHERE {conds}
      ORDER BY distance, parent_id, ou_id
    """.format(
        cte=get_recursive_ou_cte(direction=DIRECTION_PARENTS),
        conds=" AND ".join(conds),
    )
    return db.query(stmt, binds)
