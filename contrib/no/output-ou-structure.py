#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2011 University of Oslo, Norway
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

"""Output information about OU structure in a certain perspective.

This script presents the OU structure in a human-friendly fashion. We look at
either the OU structure from the specified data file OR from Cerebrum. The
latter version fetches additional data (such as associated people affiliations).
"""

import copy
import getopt
import sys

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.modules.xmlutils.system2parser import system2parser



class Node(object):
    """OU-representation for this script."""

    def _build_ids(self, ids):
        """Normalize the IDs for the node."""

        def stringify(obj):
            if isinstance(obj, (int, long)):
                return "%02d" % obj
            return str(obj)

        result = set()
        if not isinstance(ids, (set, list, tuple)):
            ids = [ids,]

        for entry in ids:
            if isinstance(entry, (list, set, tuple)):
                entry = "".join(stringify(x) for x in entry)
            result.add(entry)
            
        result.add(self.node_id)
        return result
    # end _build_ids

    
    def __init__(self, node_id, acronym, parent_id, all_ids=None):
        self.node_id = node_id
        self.acronym = acronym

        self._all_ids = self._build_ids(all_ids)
        self._parent_id = parent_id
        self._parent = None
        self._children = dict()
    # end __init__


    def add_child(self, child_node):
        """Add a child node to this Node.

        Also fix up parent/child pointers in both nodes.
        """

        if child_node.node_id == self.node_id:
            return

        if child_node not in self._children:
            self._children[child_node] = child_node

        child_node._parent = self
        assert self.node_id == child_node._parent_id
    # end add_child


    def __hash__(self):
        return hash(self.node_id)
    # end __hash__
    

    def __eq__(self, other):
        if self.__class__ != other.__class__:
            return False

        return self._all_ids == other._all_ids
    # end __eq__


    def __str__(self):
        return "%s %s (ids=%s) %d child(ren)" % (
            self.node_id, self.acronym,
            tuple(x for x in self._all_ids if x != self.node_id),
            len(self._children))
    # end __str__
        
    
    def children(self):
        """Return all children nodes sorted by node_id."""
        
        values = list(self._children.itervalues())
        return sorted(values,
                      cmp=lambda x, y: cmp(x.node_id, y.node_id))
    # end children
# end Node
        


def build_node_from_file(xml_ou):
    """Build an output node from XML data on file

    @param xml_ou:
      A representation of the XML OU data on file -- xml2object.DataOU instance. 
    """

    node_id = "%02d%02d%02d" % xml_ou.get_id(xml_ou.NO_SKO)
    acronym = xml_ou.get_name(xml_ou.NAME_ACRONYM)
    if acronym:
        acronym = acronym.value
    if xml_ou.parent:
        parent_id = "%02d%02d%02d" % xml_ou.parent[1]
        assert xml_ou.parent[0] == xml_ou.NO_SKO
    else:
        parent_id = None

    return Node(node_id, acronym, parent_id,
                tuple(x[1] for x in xml_ou.iterids()))
# end build_node_from_file



def build_tree_from_file(source_system, source_file):
    """Scan the source file and build an OU tree structure for that file."""

    const = Factory.get("Constants")()
    source = const.human2constant(source_system, const.AuthoritativeSystem)
    parser = system2parser(str(source)) or system2parser(source_system)
    if not parser:
        raise RuntimeError("Cannot determine source system from %s" %
                           str(source_system))
    parser = parser(source_file, None)

    nodes = dict()
    for xml_ou in parser.iter_ou():
        node = build_node_from_file(xml_ou)
        nodes[node.node_id] = node

    # Re-link parent information and return the root set -- all root OUs.
    # Sweep nodes, collect all those without parent_id
    root_set = set()
    for node_id in nodes:
        node = nodes[node_id]
        if (not node._parent_id) or (node.node_id == node._parent_id):
            root_set.add(node)

        parent_node = nodes[node._parent_id]
        parent_node.add_child(node)

    print "Collected %d nodes (%d in the root set)" % (len(nodes),
                                                       len(root_set))
    return root_set
# end build_tree_from_file
    

def output_tree(root_set, indent=0):
    """Output a tree in a human-friendly fashion."""

    prefix = "  "
    for node in root_set:
        print "%s[%d] %s" % (prefix*indent, indent, str(node))
        output_tree(node.children(), indent+1)
# end output_tree


def main():
    opts, args = getopt.getopt(sys.argv[1:],
                               "f:p:",
                               ("file=",
                                "perspective=",))

    source_system = None
    source_file = None
    perspective = None
    for option, value in opts:
        if option in ("-f", "--file",):
            source_system, source_file = value.split(":", 1)
        elif option in ("-p", "--perspective",):
            perspective = value
    
    assert not (source_file and perspective), \
           "You cannot specify *both* perspective and source"

    if source_file:
        root_set = build_tree_from_file(source_system, source_file)
    else:
        root_set = build_tree_from_db(perspective)

    output_tree(root_set)
# end main



if __name__ == "__main__":
    main()
