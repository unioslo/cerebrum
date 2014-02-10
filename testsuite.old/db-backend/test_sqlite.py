#!/usr/bin/env python
# -*- encoding: iso-8859-1 -*-

"""This file sets up the environment for the sqlite backend.
"""

from common import DBTestBase
from common import sneaky_import

class test_SQLite(DBTestBase):
    def setup(self):
        if not self.db_class:
            db_mod = sneaky_import("Cerebrum.Database", True)
            DBTestBase.db_class = db_mod.SQLite

        self.db = self.db_class(service=":memory:")
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

        assert x.encode("latin-1") == mark
    # end test_support_Norwegian_chars

    def test_char_is_unicode(self):
        """Check that fetching from char returns unicode objects"""

        self.db.execute("""
        CREATE TABLE nosetest1 (
        field1	CHAR VARYING (100) NOT NULL
        )
        """)

        mark = "Ich bin schnappi"
        self.db.execute("""
        INSERT INTO  [:table schema=cerebrum name=nosetest1] (field1)
        VALUES ('%s') 
        """ % mark)

        x = self.db.query_1("""
        SELECT field1
        FROM [:table schema=cerebrum name=nosetest1]
        WHERE field1 = '%s'
        """ % mark)

        assert isinstance(x, unicode)
    # end test_char_is_unicode
# end test_SQLite
