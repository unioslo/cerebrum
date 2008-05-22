#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2008 University of Oslo, Norway
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

import cerebrum_path
import sys
from Cerebrum.Utils import Factory


db=Factory.get("Database")()
db.cl_init(change_program="import_groupgroups")
gr=Factory.get("Group")(db)
memb=Factory.get("Group")(db)

file=sys.argv[1]

for l in open(file).readlines():
    l = l.split("#")[0].strip()
    if l == "": continue
    parent, children = l.split(":")
    children = children.split(",")
    gr.clear()
    gr.find_by_name(parent)
    for c in children:
        memb.clear()
        memb.find_by_name(c)
        if not gr.has_member(memb.entity_id, memb.entity_type,
                             gr.const.group_memberop_union):
            gr.add_member(memb.entity_id, memb.entity_type,
                          gr.const.group_memberop_union)
    gr.write_db()
db.commit()
