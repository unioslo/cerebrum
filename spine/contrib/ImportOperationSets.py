#!/usr/bin/env python

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
