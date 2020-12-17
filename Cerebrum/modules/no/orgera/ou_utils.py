# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
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
Queries for effectively traversing the ou_structure.

The core of this module is a CTE for traversing the ``ou_structure`` table
using a given ou_id starting point, and a given ou perspective.
"""
from __future__ import print_function, unicode_literals

import cereconf
from Cerebrum.Utils import Factory


# Template query for `get_recursive_ou_cte()`
_recursive_ou_query_fmt = """
  WITH RECURSIVE {table_name}(ou_id, parent_id, distance) AS (
    SELECT
      init.ou_id,
      init.parent_id,
      1 as distance
    FROM [:table schema=cerebrum name=ou_structure] init
    WHERE
      init.{target} = :{bind_ou}
    UNION ALL
    SELECT
      cur.ou_id,
      cur.parent_id,
      distance + 1
    FROM [:table schema=cerebrum name=ou_structure] cur
    JOIN {table_name}
    ON {ou_join_cond}
      AND cur.perspective = :{bind_perspective}
      AND cur.parent_id IS NOT NULL
    WHERE
      distance < :{bind_limit}
  )
"""


def get_recursive_ou_cte(
        parents=False,
        table_name='ou_tree',
        bind_ou='ou_id',
        bind_perspective='perspective',
        bind_limit='max_distance'):
    """
    Get a recursive ou common table expression (CTE)

    :param bool parents:
        `True` - find parents, `False` - find children

    :param str table_name:
        Name of the recursive query - default: ou_tree

    :param str bind_ou:
        Name of the initial ou binding - default: ou_id

    :param str bind_perspective:
        Name of the ou perspective binding - default: perspective

    :param str bind_limit:
        Name of the recursion limit binding - default: max_distance

    :returns str:
        Returns a ou tree CTE for use in other queries.

    The resulting CTE string can be used much like a regular table.  When used
    in a query, it needs three extra binds to be provided:

    - <bind_ou>: the initial ou to start the search at
    - <bind_perspective>: the ou_perspective to use in recursion
    - <bind_distance>: recursion limit for the query
    """
    return _recursive_ou_query_fmt.format(
        table_name=table_name,
        target=(
            'ou_id'
            if parents else
            'parent_id'
        ),
        ou_join_cond=(
            'cur.ou_id = {table_name}.parent_id'
            if parents else
            'cur.parent_id = {table_name}.ou_id'
        ).format(table_name=table_name),
        bind_ou=bind_ou,
        bind_perspective=bind_perspective,
        bind_limit=bind_limit,
    )


def find_children(db, perspective, ou_id, max_distance=100):
    """ Recursively find all children of a given ou.

    :param db:
    :param perspective: perspective for the search
    :param ou_id: root ou for the search
    :param max_distance: max distance from the root ou

    :returns:
        Rows of child ous (ou_id, parent_id, distance).

        - ``ou_id`` is the id of a child ou
        - ``parent_id`` is the immediate parent of ``ou_id``
        - ``distance`` is the number of parent *hops* to the root ou.

        ``distance == 1`` when ``parent_id`` == ``ou_id``
    """
    stmt = """
      {cte}
      SELECT ou_id, parent_id, distance
      FROM ou_tree
    """.format(cte=get_recursive_ou_cte(parents=False))

    binds = {
        'max_distance': int(max_distance),
        'ou_id': int(ou_id),
        'perspective': int(perspective),
    }
    return db.query(stmt, binds)


def find_parents(db, perspective, ou_id, max_distance=100):
    """ Recursively find all parents of a given ou.

    :param db:
    :param perspective: perspective for the search
    :param ou_id: leaf ou for the search
    :param max_distance: max distance from the leaf ou

    :returns: A tuple of parent ou ids
        Rows of parent ous (ou_id, child_id, distance).
    """
    stmt = """
      {cte}
      SELECT parent_id as ou_id, ou_id as child_id, distance
      FROM ou_tree
    """.format(cte=get_recursive_ou_cte(parents=True))

    binds = {
        'max_distance': int(max_distance),
        'ou_id': int(ou_id),
        'perspective': int(perspective),
    }
    return db.query(stmt, binds)


def list_roots(db, perspective):
    stmt = """
      SELECT ou_id
      FROM [:table schema=cerebrum name=ou_structure]
      WHERE parent_id IS NULL
    """
    return tuple(int(r['ou_id']) for r in db.query(stmt))


def get_ou_by_sko(db, sko):
    """
    Fetch an OU object by stedkode
    """
    if len(sko) != 6 or not sko.isdigit():
        raise ValueError('Invalid stedkode: %s' % repr(sko))

    ou = Factory.get('OU')(db)
    ou.find_stedkode(
        fakultet=int(sko[:2]),
        institutt=int(sko[2:4]),
        avdeling=int(sko[4:6]),
        institusjon=int(cereconf.DEFAULT_INSTITUSJONSNR),
    )
    return ou
