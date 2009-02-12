#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""This file sets up the environment for the cx_Oracle backend.

For this test we'll need this environment:

* In cereconf.py:

  DB_AUTH_DIR=<suitable dir with passords to the db>
  CEREBRUM_DATABASE_NAME = <whatever>
  CEREBRUM_DATABASE_CONNECT_DATA['user'] = <whatever>

For Cerebrum @UiO, user=cerebrum_test, database=hk8utv.uio.no is a good start.

* Oracle environment. Check your Oracle documentation for what to do.
"""

from os.path import exists
from os import getenv

from common import DBTestBase
from common import sneaky_import



class test_cxOracle(DBTestBase):

    def __init__(self):
        super(test_cxOracle, self).__init__()
        # our testdb has no schema.
        self.schema = None
    # end __init__
    
    def setup(self):
        if not self.db_class:
            import cereconf
            db_mod = sneaky_import("Cerebrum.Database")

            # This is the environment that must be present
            # Oracle stuff
            assert getenv("ORACLE_HOME"), "No oracle environment present"

            assert hasattr(cereconf, "CEREBRUM_DATABASE_CONNECT_DATA")

            assert ((hasattr(cereconf, "DB_AUTH_DIR") and
                     exists(cereconf.DB_AUTH_DIR)) or
                    ("password" in cereconf.CEREBRUM_DATABASE_CONNECT_DATA))

            assert hasattr(cereconf, "CEREBRUM_DATABASE_NAME"), \
                   "Set CEREBRUM_DATABASE_NAME to something useful"

            assert "user" in cereconf.CEREBRUM_DATABASE_CONNECT_DATA, \
                   "Missing 'user' in CEREBRUM_DATABASE_CONNECT_DATA"

            DBTestBase.db_class = db_mod.cx_Oracle

        self.db = self.db_class()
        self.db.execute("set transaction isolation level serializable")
        for tname in ("nosetest2", "nosetest1"):
            try:
                self.db.execute("drop table %s" % tname)
            except self.db.DatabaseError:
                pass
            
        for sname in ("nosetest1",):
            try:
                self.db.execute("drop sequence %s" % sname)
            except self.db.DatabaseError:
                pass

    # end setup

    def teardown(self):
        self.db.rollback()
        self.db.close()
    # end teardown

# end class test_cxOracle
