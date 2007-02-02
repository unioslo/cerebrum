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

db_user = cereconf.CEREBRUM_DATABASE_CONNECT_DATA['table_owner']
if db_user is None:
    db_user = cereconf.CEREBRUM_DATABASE_CONNECT_DATA['user']
    if db_user is not None:
        print "'table_owner' not set in CEREBRUM_DATABASE_CONNECT_DATA."
        print "Will use regular 'user' (%s) instead." % db_user

def create_op_set(set_name, op_codestrs):
    db = Factory.get('Database')(user=db_user)
    auth_op_set = BofhdAuthOpSet(db)
    try:
        auth_op_set.find_by_name(set_name)
        # Get the auth_op_codes already in the set.
        existing = [x[0] for x in auth_op_set.list_operations()]
    except NotFoundError, e:
        auth_op_set.populate(set_name)
        auth_op_set.write_db()
        existing = []
    for codestr in op_codestrs:
        code = _AuthRoleOpCode(codestr)
        if not int(code) in existing:
            auth_op_set.add_operation(int(code))
            existing.append(int(code))
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
    operation_sets = __import__(file[:-3]).operation_sets
    for name, d in operation_sets.items():
        create_op_set(name, d['codestrs'])
