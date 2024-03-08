# encoding: utf-8
#
# Copyright 2024 University of Oslo, Norway
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
Unit tests for *Cerebrum.org.perspective_db*
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

import Cerebrum.Errors
import Cerebrum.OU
import Cerebrum.database.errors
from Cerebrum.org import perspective_db as pdb
from Cerebrum.testutils import datasource


@pytest.fixture
def database(database):
    """ A database-object, with change_program set. """
    database.cl_init(change_program='test_perspective_db')
    return database


@pytest.fixture
def perspective(constant_module):
    """ A new, unique perspective setting. """
    code = constant_module._OUPerspectiveCode
    p = code("test-org-tree",
             description="Org tree for test_perspective_db unit test")
    p.insert()
    return p


def _create_org_units(db, limit=5):
    """ Basic populator function for org units.  """
    ou_ids = list()
    ou = Cerebrum.OU.OU(db)
    for e in datasource.BasicOUSource()(limit=limit):
        try:
            ou.populate()
            ou.write_db()
            ou_ids.append(ou.entity_id)
        except Exception:
            db.rollback()
            raise
        finally:
            ou.clear()
    return ou_ids


#
# Basic tests
#

def test_set_root(database, perspective):
    ou_id = _create_org_units(database, 1)[0]
    pdb.set_parent(database, perspective, ou_id, None)

    parent_id = pdb.get_parent_id(database, perspective, ou_id)
    assert parent_id is None


def test_set_parent(database, perspective):
    root_id, child_id = _create_org_units(database, 2)
    pdb.set_parent(database, perspective, root_id, None)
    pdb.set_parent(database, perspective, child_id, root_id)

    parent_id = pdb.get_parent_id(database, perspective, child_id)
    assert parent_id == root_id


def test_missing_node(database, perspective):
    """ only org units present in *perspective* can be parents. """
    parent_id, child_id = _create_org_units(database, 2)
    with pytest.raises(Cerebrum.database.errors.IntegrityError):
        # parent_id isn't present in the perspective, and as such, not actually
        # an org tree node yet
        pdb.set_parent(database, perspective, child_id, parent_id)


#
# For the remaining tests, we'll need an ou tree.
#
# The create 8 org units, A-H, and set up the following tree structure:
#
#     +- A
#     |  +- B
#     |  |  +- C
#     |  |
#     |  +- D
#     |     +- E
#     |     +- F
#     |     +- G
#     |
#     +- H
#

# indices in *ou_tree* return value
A, B, C, D, E, F, G, H = range(8)

# (child_index, parent_index) tuples for *ou_tree*
RELATIONSHIPS = [(A, None), (B, A), (C, B), (D, A),
                 (E, D), (F, D), (G, D), (H, None)]


def _map_relationship_ids(ou_ids):
    """ translate RELATIONSHIPS from *ou_tree* indices to ou ids. """
    return [
        (ou_ids[child_idx], None if parent_idx is None else ou_ids[parent_idx])
        for child_idx, parent_idx in RELATIONSHIPS
    ]


@pytest.fixture
def ou_tree(database, perspective):
    """ Creates and returns *ou_ids* of the org units from RELATIONSHIPS.  """
    ou_ids = _create_org_units(database, len(RELATIONSHIPS))
    for child_id, parent_id in _map_relationship_ids(ou_ids):
        pdb.set_parent(database, perspective, child_id, parent_id)
    return ou_ids


def test_get_parent_map(database, perspective, ou_tree):
    """ get_parent_map should return all relationships in perspective. """
    expected = dict(_map_relationship_ids(ou_tree))
    ou_map = pdb.get_parent_map(database, perspective)
    assert ou_map == expected


def test_list_roots(database, perspective, ou_tree):
    """ list_roots should return the id of all root nodes in perspective. """
    expected = set((ou_tree[A], ou_tree[H]))
    root_ids = pdb.list_roots(database, perspective)
    assert root_ids == expected


def test_clear_parent(database, perspective, ou_tree):
    """ clear_parent should remove a leaf node from the tree. """
    leaf_node = ou_tree[G]
    pdb.clear_parent(database, perspective, leaf_node)
    with pytest.raises(Cerebrum.Errors.NotFoundError):
        # the leaf_node should no longer be present in perspective
        pdb.get_parent_id(database, perspective, leaf_node)


def test_remove_parent_from_tree(database, perspective, ou_tree):
    """ clear_parent should not be able to remove a node with children. """
    node = ou_tree[D]
    with pytest.raises(Cerebrum.database.errors.IntegrityError):
        # all parents *must* exist in the org tree, and removing a parent with
        # children should fail.
        pdb.clear_parent(database, perspective, node)


def test_move_ou(database, perspective, ou_tree):
    """ set_parent should be able to move an existing leaf node. """
    node = ou_tree[E]
    old_parent = ou_tree[D]
    new_parent = ou_tree[B]

    # quick sanity check of our test-tree
    assert pdb.get_parent_id(database, perspective, node) == old_parent

    # move node to new_parent
    pdb.set_parent(database, perspective, node, new_parent)
    assert pdb.get_parent_id(database, perspective, node) == new_parent


#
# Recursive searches
#


def test_find_children_a(database, perspective, ou_tree):
    """ find_children should return all children of a root node. """
    node = ou_tree[A]
    expected = set(ou_tree[v] for v in (B, C, D, E, F, G))
    assert set(
        row['ou_id']
        for row in pdb.find_children(database, perspective, node)
    ) == expected


def test_find_children_d(database, perspective, ou_tree):
    """ find_children should return all children of a non-root node. """
    node = ou_tree[D]
    expected = set(ou_tree[v] for v in (E, F, G))
    assert set(
        row['ou_id']
        for row in pdb.find_children(database, perspective, node)
    ) == expected


def test_find_children_depth(database, perspective, ou_tree):
    """ find_children should only return direct children when depth=1. """
    node = ou_tree[A]
    expected = set(ou_tree[v] for v in (B, D))
    assert set(
        row['ou_id']
        for row in pdb.find_children(database, perspective, node, depth=1)
    ) == expected


def test_find_children_leaf(database, perspective, ou_tree):
    """ find_children should not return any results for leaf nodes. """
    leaf_node = ou_tree[H]
    assert not set(
        row['ou_id']
        for row in pdb.find_children(database, perspective, leaf_node)
    )


def test_find_parents_g(database, perspective, ou_tree):
    """ find_parents should return all nodes in the path to a leaf node. """
    node = ou_tree[G]
    expected = set(ou_tree[v] for v in (D, A))
    assert set(
        row['parent_id']
        for row in pdb.find_parents(database, perspective, node)
    ) == expected


def test_find_parents_d(database, perspective, ou_tree):
    """ find_parents should return all parents of any node. """
    node = ou_tree[D]
    expected = set(ou_tree[v] for v in (A,))
    assert set(
        row['parent_id']
        for row in pdb.find_parents(database, perspective, node)
    ) == expected


def test_find_parents_depth(database, perspective, ou_tree):
    """ find_parents should only return direct parent when depth=1. """
    node = ou_tree[G]
    expected = set(ou_tree[v] for v in (D,))
    assert set(
        row['parent_id']
        for row in pdb.find_parents(database, perspective, node, depth=1)
    ) == expected


def test_find_parents_root(database, perspective, ou_tree):
    """ find_parents not return any results for root nodes. """
    root_node = ou_tree[H]
    assert not set(
        row['parent_id']
        for row in pdb.find_parents(database, perspective, root_node)
    )


def test_find_parents_cycle(database, perspective, ou_tree):
    """ find_parents should stop after finding a cycle. """
    root_id = ou_tree[A]
    leaf_id = ou_tree[G]

    # create a cycle: [G] -> [D] -> [A] -> [G]
    pdb.set_parent(database, perspective, root_id, leaf_id)

    # We add a depth limit here to stop in case we encounter an infinite loop.
    # The query *should* end itself after detecting a loop, but we're here to
    # test if that actually happens.
    parents = list(pdb.find_parents(database, perspective, leaf_id, depth=10))

    # Our first result should be the parent for our *leaf_id*
    assert parents[0]['ou_id'] == leaf_id

    # Our last result should be the second time we see that same parent
    assert parents[-1]['ou_id'] == leaf_id

    # Our original tree had a max distance of 2 ([G->D], [D->A]).  With our
    # cycle, we now have 3 unique relationships, and abort on the 4th where we
    # identify the cycle ([G->D], [D->A], [A->G], [G->D]).
    assert parents[-1]['distance'] == 4


def test_find_children_cycle(database, perspective, ou_tree):
    """ find_children should stop after finding a cycle. """
    root_id = ou_tree[A]
    leaf_id = ou_tree[G]

    # See test_find_parents_cycle() for details.  This is the same test in
    # reverse.
    pdb.set_parent(database, perspective, root_id, leaf_id)
    children = list(pdb.find_children(database, perspective, root_id,
                                      depth=10))
    assert children[0]['parent_id'] == root_id
    assert children[-1]['parent_id'] == root_id
    assert children[-1]['distance'] == 4
