#!/usr/bin/env python
# -*- encoding: iso-8859-1 -*-

"""This file sets up the environment for the psycopg 1.x backend.

For this test to work we'll need this environment:

* In cereconf.py:

  DB_AUTH_DIR=<suitable dir with passwords to the db>
  CEREBRUM_DATABASE_NAME = <whatever>
  CEREBRUM_DATABASE_CONNECT_DATA['user'] = <whatever>
  CEREBRUM_DATABASE_CONNECT_DATA['host'] = <whatever>

For Cerebrum @UiO, user=cerebrum, host=dbpg-cere-utv.uio.no is quite
practical.
"""
from os.path import exists

from common import DBTestBase
from common import sneaky_import


class test_PsycoPG1(DBTestBase):

    def setup(self):
        """Establish a connection to the database."""

        if not self.db_class:
            import cereconf
            db_mod = sneaky_import("Cerebrum.Database")

            # This is the environment that *must* be present.
            # They cannot really be guessed or somehow faked.
            assert exists(cereconf.DB_AUTH_DIR), \
                "DB_AUTH_DIR points to non-existing directory"
            assert hasattr(cereconf, "CEREBRUM_DATABASE_NAME"), \
                "Set CEREBRUM_DATABASE_NAME to something useful"
            assert hasattr(cereconf, "CEREBRUM_DATABASE_CONNECT_DATA")
            assert "user" in cereconf.CEREBRUM_DATABASE_CONNECT_DATA, \
                   "Missing 'user' in CEREBRUM_DATABASE_CONNECT_DATA"
            assert (hasattr(cereconf, "DB_AUTH_DIR") or
                    "password" in cereconf.CEREBRUM_DATABASE_CONNECT_DATA)
            assert "host" in cereconf.CEREBRUM_DATABASE_CONNECT_DATA, \
                   "Missing 'host' in CEREBRUM_DATABASE_CONNECT_DATA"

            DBTestBase.db_class = db_mod.PsycoPG

        self.db = self.db_class()
        self.db._db.set_isolation_level(3)
    # end setup

    def teardown(self):
        self.db.rollback()
        self.db.close()
    # end teardown

    def test_support_Norwegian_chars(self):
        """Make sure we can use Norwegian chars"""

        self.db.execute("""
        CREATE TABLE nosetest1 (
        field1	CHAR VARYING (100) NOT NULL
        )
        """)

        mark = "Blåbærsyltetøy"
        self.db.execute("""
        INSERT INTO  [:table schema=cerebrum name=nosetest1] (field1)
        VALUES (:value1)
        """, {"value1": mark})

        x = self.db.query_1("""
        SELECT field1
        FROM [:table schema=cerebrum name=nosetest1]
        WHERE field1 = :value
        """, {"value": mark})

        assert x == mark
    # end test_support_Norwegian_chars
# end test_PsycoPG
