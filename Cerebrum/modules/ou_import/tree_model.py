# -*- coding: utf-8 -*-
#
# Copyright 2022-2024 University of Oslo, Norway
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
Abstract model of a tree structure.

Trees must be built using two passes:

1. First pass builds the individual node structures, and builds a node_id to
   node mapping for parent lookups in the next pass.

2. Second pass updates the node parent/child pointers, finds cycles, and finds
   root nodes.


A typical implementation for building a tree would look something like:

1. Gather raw data - here each tuple is a (node_id, parent_id) pair.

>>> raw_nodes = [(2, 1), (3, 2), (4, 2), (5, 3)]

2. Build node objects for each node.  Note that first node points to an invalid
   (non-existing node_id).  This means it will turn into a root node (no valid
   parent) in the *next* step.

>>> nodes = [Node(*args) for args in raw_nodes]

2. Build tree structure.  This goes through all nodes, and updates the
   node.parent and node.children references in each node object.
   The return value is a tuple of all nodes where the parent node was not
   present in the *nodes* list.  These nodes are the roots of our tree
   structures.

>>> roots = build_trees(nodes)
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

from Cerebrum.utils import reprutils


logger = logging.getLogger(__name__)


class Node(reprutils.ReprFieldMixin):
    """ Generic tree node. """

    repr_fields = ('node_id', 'parent_id')
    repr_id = False
    repr_module = False

    def __init__(self, node_id, parent_id=None, node_data=None):
        self.node_id = node_id
        self.parent_id = parent_id
        self.node_data = node_data
        self._parent = None
        self._children = set()

    @property
    def path(self):
        """ all nodes sepratating this node from a root. """
        if self.parent is None:
            return tuple()
        else:
            return (self.parent,) + self.parent.path

    @property
    def parent(self):
        """ parent reference """
        return self._parent

    @parent.setter
    def parent(self, new_parent):
        old_parent = self._parent

        if new_parent is self:
            raise AttributeError("cannot set self as parent")

        # check for potential cycle
        if new_parent is not None:
            if self in new_parent.path:
                raise AttributeError(
                    "cycle detected in node %r: %r" %
                    (repr(self), " -> ".join([repr(s) for s in
                                              new_parent.path])))

        # TODO: Here we start updates - if any exception is raised here, we may
        # end up in a briken state.  We should make these updates atomic:
        if old_parent is not None:
            old_parent._children.remove(self)
        if new_parent is not None:
            new_parent._children.add(self)
        self._parent = new_parent

    @parent.deleter
    def parent(self):
        self.parent = None

    @property
    def children(self):
        """ child references """
        return tuple(self._children)


def build_trees(nodes):
    """
    Build a node hierarchy.

    :param iterable nodes: An iterable with Node objects.

    :return tuple: Returns a tuple of root OUs.
    """

    # Index all ous
    index = dict()
    for node in nodes:
        if node.node_id in index:
            logger.warn('Duplicate node with node_id=%r', node.node_id)
        index[node.node_id] = node

    # Build ou hierarchies
    roots = []
    for node in index.values():
        if node.parent_id is None:
            roots.append(node)
        else:
            try:
                node.parent = index[node.parent_id]
            except KeyError:
                logger.error("No parent ou %r for %r",
                             node.parent_id, node.node_id)
                node.parent_id = None
                roots.append(node)
    return tuple(roots)
