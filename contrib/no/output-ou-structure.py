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

from collections import deque
import getopt
import sys

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.modules.xmlutils.system2parser import system2parser



def sko2str(fak, inst, grp):
    return "%02d%02d%02d" % (fak, inst, grp)
# end sko2str



def build_ids(seq):
    """Try to normalize a bunch of ids.

    Return a sequence of str representing identifications in seq.

    seq can be a sequence of <T> or a sequence of pairs (x, y), where x is id
    tag and y the id itself.
    """

    def stringify(obj):
        if isinstance(obj, (int, long)):
            if 0 <= obj < 100:
                return "%02d" % obj
        elif isinstance(obj, (list, tuple, set)):
            return "".join(stringify(x) for x in obj)
        return str(obj)

    result = set()
    if not isinstance(seq, (set, list, tuple)):
        seq = [seq,]

    for entry in seq:
        if isinstance(entry, (list, tuple)) and len(entry) == 2:
            entry = "%s=%s" % (stringify(entry[0]), stringify(entry[1]))
        elif isinstance(entry, (list, set, tuple)):
            entry = "".join(stringify(x) for x in entry)
        else:
            entry = stringify(entry)
        result.add(entry)
            
    return result
# end build_ids



def sort_nodes(node_seq):
    """Return the same sequence, but sorted by node_id."""
    
    return sorted(node_seq,
                  cmp=lambda x, y: cmp(x.node_id, y.node_id))
# end sort_nodes



def set_has_cycles(nodes):
    """Determine if the node set has cycles in it."""

    processed = set()
    def dump_cycle(n):
        """Print a cycle initiated at node n."""

        print "Cycle detected at node", n
        tmp = n
        while tmp.parent_id != n.node_id:
            print "->", tmp
            tmp = tmp.parent
    # end dump_cycle
    
    if not nodes:
        return 

    # Collect roots, if any
    queue = deque(x for x in nodes.itervalues()
                  if x.parent_id is None or x.parent_id == x.node_id)
    # If we don't have a root set, than NO matter where we start, the WILL be a
    # cycle. There may be multiple cycles, but there is at least one.
    if not queue:
        k, v = nodes.popitem()
        nodes[k] = v
        queue.append(v)

    # let's go -- BFS
    while queue:
        n = queue.popleft()
        if n in processed:
            dump_cycle(n)
        else:
            queue.extend(n.children())
            processed.add(n)

    # Ok, the work queue is empty. What happened?
    if len(processed) != len(nodes):
        print "%d OUs have not been reached. Cyclic dependency below?" % (
            len(nodes) - len(processed))
        for node in nodes.itervalues():
            if node not in processed:
                print "\t%s" % (node,)
        return True

    return False
# end check_cycles



class Node(object):
    """OU-representation for this script."""

    def __init__(self, node_id, name, acronym, parent_id, all_ids=None):
        self.node_id = node_id
        self.name = name
        self.acronym = acronym

        self._all_ids = build_ids(all_ids)
        self.parent_id = parent_id
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
        assert self.node_id == child_node.parent_id
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
        return "%s %s %s %d child node(s)" % (
            self.node_id, self.name,
            sorted(tuple(x for x in self._all_ids if x != self.node_id)),
            len(self._children))
    # end __str__


    def typeset(self, boss_mode):
        """Create a human-friendly representation of self."""
        if boss_mode:
            return "%s %s %d child node(s)" % (self.node_id, self.name,
                                               len(self._children))
        return str(self)
    # end typeset
    
    
    def children(self):
        """Return all children nodes sorted by node_id."""
        
        return sort_nodes(list(self._children.itervalues()))
    # end children
# end Node
        


def build_node_from_file(xml_ou):
    """Build an output node from XML data on file

    @param xml_ou:
      A representation of the XML OU data on file -- xml2object.DataOU instance.
    """

    node_id = sko2str(*xml_ou.get_id(xml_ou.NO_SKO))
    acronym = xml_ou.get_name(xml_ou.NAME_ACRONYM)
    if acronym:
        acronym = acronym.value
    name = xml_ou.get_name(xml_ou.NAME_LONG) or xml_ou.get_name(xml_ou.NAME_SHORT)
    if name:
        name = name.value
    if xml_ou.parent:
        parent_id = sko2str(*xml_ou.parent[1])
        assert xml_ou.parent[0] == xml_ou.NO_SKO
    else:
        parent_id = None

    return Node(node_id, name, acronym, parent_id, tuple(xml_ou.iterids()))
# end build_node_from_file



def create_root_set(nodes):
    """Link up all the parent-child nodes and return the resulting root set."""

    # Re-link parent information and return the root set -- all root OUs.
    # Sweep nodes, collect all those without parent_id
    root_set = set()
    for node_id in nodes:
        node = nodes[node_id]
        if (not node.parent_id) or (node.node_id == node.parent_id):
            root_set.add(node)

        parent_node = nodes.get(node.parent_id)
        if parent_node:
            parent_node.add_child(node)

    print "Collected %d nodes (%d in the root set)" % (len(nodes),
                                                       len(root_set))
    return root_set
# end create_root_set



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

    rs = create_root_set(nodes)
    if set_has_cycles(nodes):
        return set()
    return rs
# end build_tree_from_file
    


def build_tree_from_db(ou_perspective):
    """Use Cerebrum as source to build an OU root set."""

    const = Factory.get("Constants")()
    db = Factory.get("Database")()
    perspective = const.human2constant(ou_perspective,
                                       const.OUPerspective)
    if not perspective:
        print "No match for perspective «%s». Available options: %s" % (
            ou_perspective,
            ", ".join(str(x)
                      for x in const.fetch_constants(const.OUPerspective)))
        return set()
        
    ou = Factory.get("OU")(db)
    ou_id2sko = dict((r["ou_id"], sko2str(r["fakultet"],
                                          r["institutt"],
                                          r["avdeling"]))
                     for r in ou.get_stedkoder())
    nodes = dict()
    for row in ou.search():
        ou.clear()
        ou.find(row["ou_id"])
        sko = sko2str(ou.fakultet, ou.institutt, ou.avdeling)
        ids = set((("id", ou.entity_id), ("sko", sko)))
        ids.update((str(const.EntityExternalId(x["id_type"])), x["external_id"])
                   for x in ou.get_external_id())
        try:
            parent = ou_id2sko.get(ou.get_parent(perspective))
        except:
            parent = None
        
        node = Node(sko, ou.name, ou.acronym, parent, ids)
        nodes[node.node_id] = node

    rs = create_root_set(nodes)
    if set_has_cycles(nodes):
        return set()
    return rs
# end build_tree_from_db



def output_tree(root_set, boss_mode, indent=0):
    """Output a tree in a human-friendly fashion."""

    prefix = "  "
    for node in sort_nodes(root_set):
        print "%s[%d] %s" % (prefix*indent, indent+1, node.typeset(boss_mode))
        output_tree(node.children(), boss_mode, indent+1)
# end output_tree



def main():
    opts, args = getopt.getopt(sys.argv[1:],
                               "f:p:b",
                               ("file=",
                                "perspective=",
                                "boss-mode",))

    source_system = None
    source_file = None
    perspective = None
    boss_mode = False
    for option, value in opts:
        if option in ("-f", "--file",):
            source_system, source_file = value.split(":", 1)
        elif option in ("-p", "--perspective",):
            perspective = value
        elif option in ("-b", "--boss-mode",):
            boss_mode = True
    
    assert not (source_file and perspective), \
           "You cannot specify *both* perspective and source"

    if source_file:
        root_set = build_tree_from_file(source_system, source_file)
    else:
        root_set = build_tree_from_db(perspective)

    output_tree(root_set, boss_mode)
# end main



if __name__ == "__main__":
    main()
