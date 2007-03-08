#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2004-2006 University of Oslo, Norway
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

import os
import sys
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Constants
from sets import Set
from Cerebrum.Errors import NotFoundError
from Cerebrum.spine.SpineLib import Builder
from Cerebrum.modules.bofhd.utils import _AuthRoleOpCode
from Cerebrum.modules.bofhd.auth import BofhdAuthOpSet
from Cerebrum.modules.bofhd.auth import BofhdAuthOpTarget

db_user = cereconf.CEREBRUM_DATABASE_CONNECT_DATA['table_owner']
if db_user is None:
    db_user = cereconf.CEREBRUM_DATABASE_CONNECT_DATA['user']
    if db_user is not None:
        print "'table_owner' not set in CEREBRUM_DATABASE_CONNECT_DATA."
        print "Will use regular 'user' (%s) instead." % db_user

def create_op_sets(operation_sets):
    op_sets_added = []
    db = Factory.get('Database')(user=db_user)
    auth_op_set = BofhdAuthOpSet(db)
    e_op_sets = dict([(x[1], x[0]) for x in auth_op_set.list()])
    for name, op_codestrs in operation_sets.items():
        op_codestrs = op_codestrs['codestrs']
        if name in e_op_sets:
            auth_op_set.find(e_op_sets[name])
            existing = [x[0] for x in auth_op_set.list_operations()]
        else:
            auth_op_set.clear()
            auth_op_set.populate(name)
            auth_op_set.write_db()
            existing = []

        added_codes = []

        for codestr in op_codestrs:
            code = int(_AuthRoleOpCode(codestr))
            added_codes.append(code)
            if not code in existing:
                auth_op_set.add_operation(code)
                existing.append(code)

        for code in existing:
            if not code in added_codes:
                auth_op_set.del_operation(code)

    db.commit()

def create_op_targets(targets):
    targets_added = []
    db = Factory.get('Database')(user=db_user)
    target = BofhdAuthOpTarget(db)
    for t in targets:
        existing = target.list(target_type=t[0],
                               entity_id=t[1],
                               attr=t[2])
        if len(existing) == 0:
            target.clear()
            target.populate(t[1], t[0], t[2])
            target.write_db()
            targets_added.append(target.list(target.op_target_id)[0])
        else:
            targets_added.append(existing[0])
    target.clear()
    for t in target.list():
        if not t in targets_added:
            target.find(t[0])
            target.delete()
    db.commit()

if __name__ == '__main__':
    if len(sys.argv) != 2 or not os.path.isfile(sys.argv[1]):
        print "Expected a python file containing a variable named operation_sets as only argument."
        sys.exit(1)
    path = os.path.abspath(sys.argv[1])
    file = os.path.basename(path)
    if not file.endswith('.py'):
        print "Expected a python file containing a variable named operation_sets as only argument."
        sys.exit(1)
    sys.path.append(os.path.dirname(path))
    source = __import__(file[:-3])
    create_op_sets(source.operation_sets)
    create_op_targets(source.operation_targets)
