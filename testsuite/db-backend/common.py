#!/usr/bin/env python
# -*- encoding: iso-8859-1 -*-

"""This file contains code common to all DB backend testing.

I.e. all backends should be able to connect() to a database (albeit they do it
in different ways). This file captures the setup code and the tests that are
universally applicable to all backends.

If you are reading this because you want to set up tests for a new backend,
this is what you need to do:

  * Setup cereconf.py with:

      - DB_AUTH_DIR (if needed)
      - CEREBRUM_DATABASE_NAME (if needed, but probably always)
      - CEREBRUM_DATABASE_CONNECT_DATA (if needed, but probably always)

  * Make sure your PYTHONPATH points to that cereconf.py. You may chose to let
    PYTHONPATH point to a suitable cerebrum root as well, but you don't have
    to (the script will pick up the directory from its own location).

  * Write your own test class (test_Something) that inherits from ... below
    and override setup() and teardown().

In general:

* Do *NOT* test multiple features in a single method
* Do *NOT* have a failing test followed by a succeeding one in the same
  function. At different isolation levels, if a failure is detected, the
  entire transaction will be aborted! (and the succeeding test will test
  because of the failed transaction from the previous test in the same method
  which was supposed to and actually did fail)

Usage:

  #. Point PYTHONPATH to cereconf.py
  #. nosetest -d <suitable backend test file>.py
"""

import imp
import sys
from os.path import join, normpath, exists
from os import getcwd

from nose.tools import assert_raises



def sneaky_import(name, with_debug=False):
    """Import module L{name}, falling back to 'relative' import from the
    Cerebrum installation where *this* file is located. 
    """
    
    components = name.split(".")
    # first, try if it is already in the path:
    try:
        mod = __import__(name)
    except ImportError:
        # Ah, it was not in our path. In that case, let's assume that we want
        # a cerebrum module in *this* code tree
        my_path = __file__
        cerebrum_root_path = normpath(join(my_path, "../../../"))
        if cerebrum_root_path not in sys.path:
            sys.path.append(cerebrum_root_path)
        mod = __import__(name)

    for tmp_name in components[1:]:
        mod = getattr(mod, tmp_name)

    if with_debug:
        print "Imported <%s> from %s" % (name, mod.__file__)

    return mod
# end sneaky_import


class DBTestBase(object):
    """This class implements DB backend tests applicable to *ALL* backends.

    The intent is to capture the minimum of required functionality. Each
    backend can (should?) obviously implement its own tests that cover that
    backend's idiosyncrasies, but at least *this* set must be supported.

    Some of the tests require write access to the database.
    """

    # This keeps track of the Database class for the specific backend. This is
    # set up by setup().
    db_class = None

    def __init__(self):
        self.db = None

    def setup(self):
        raise NotImplementedError("You must implement setup() "
                                  "for your db-backend")

    def teardown(self):
        raise NotImplementedError("You must implement teardown() "
                                  "for your db-backend")

    def test_dbapi2(self):
        """Check that DB-API 2.0 methods are present"""

        for mem_func_name in ("close",
                              "commit",
                              "rollback",
                              "cursor",):
            assert hasattr(self.db, mem_func_name)

        cursor = self.db.cursor()
        for mem_name in ("description",
                         "rowcount",
                         "close",
                         "execute",
                         "executemany",
                         "fetchone",
                         "fetchmany",
                         "fetchall",
                         "arraysize",
                         "setinputsizes",
                         "setoutputsize",):
            assert hasattr(cursor, mem_name)
    # end test_dbapi2


    def test_db_cerebrum_api(self):
        """Test cerebrum DB-API extensions"""

        cursor = self.db.cursor()
        for mem_name in ("query", "query_1"):
            assert hasattr(cursor, mem_name)
    # end test_db_cerebrum_api


    def test_db_ping(self):
        """Check that we can ping the database"""

        self.db.ping()
    # end test_db_ping


    def test_table_create1(self):
        """Create a simple table."""

        self.db.execute("""
        CREATE TABLE nosetest1 (
        name	char varying(10),
        value   int
        )""")
    # end test_table_create1


    def test_table_all_datatypes(self):
        """Create a table with all used data types"""

        self.db.execute("""
        CREATE TABLE nosetest1 (
            field1	CHAR VARYING (10),
            field2	CHAR(20),
            field3	NUMERIC(12, 0),
            field4	DATE
        )
        """)
    # end test_table_all_datatypes

    def test_table_with_default(self):
        """Check that specifying defaults works"""

        self.db.execute("""
        CREATE TABLE nosetest1 (
            field2	CHAR(20) default 'foobar',
            field3	NUMERIC(12, 0) default 20
        )
        """)
    # end test_table_with_default


    def test_cerebrum_syntax_now(self):
        """Check Cerebrum's [:now] syntax extension"""

        self.db.execute("""
        CREATE TABLE nosetest1 (
            field1	DATE default [:now],
            field2	int
        )
        """)

        self.db.execute("""
        INSERT INTO nosetest1
        (field1, field2)
        VALUES ([:now], 20)
        """)

        self.db.query("""
        SELECT *
        FROM nosetest1
        WHERE field1 = [:now]
        """)
    # end test_cerebrum_syntax


    def test_cerebrum_syntax_table(self):
        """Check Cerebrum's [:table] syntax extension"""

        self.db.query("""
        CREATE TABLE nosetest1 (
        field1	INT,
        field2  INT
        )
        """)

        self.db.query("""
        SELECT *
        FROM [:table schema=cerebrum name=nosetest1]
        """)

        self.db.execute("""
        INSERT INTO [:table schema=cerebrum name=nosetest1] (field1, field2)
        VALUES (1, 2)
        """)
    # end test_cerebrum_syntax_table
    

    def test_sequence1(self):
        """Check that sequences exist"""

        self.db.execute("CREATE SEQUENCE nosetest1")
        x = self.db.nextval("nosetest1")
        y = self.db.nextval("nosetest1")
        assert y - x == 1
    # end test_sequence1


    def test_cerebrum_syntax_sequence(self):
        """Check Cerebrum's [:sequence_start] syntax extension."""

        start = 1000
        self.db.execute("""
        CREATE SEQUENCE nosetest1 [:sequence_start value=%d]
        """ % start)

        y = self.db.nextval("nosetest1")
        assert y - start == 1
    # end test_cerebrum_syntax_sequence

    def test_primary_key1(self):
        """Check that PKs can be specified"""

        self.db.execute("""
        CREATE TABLE nosetest1 (
        foo	INT	NOT NULL
                CONSTRAINT nosetest1_pk PRIMARY KEY,
        bar	INT	NOT NULL
        )
        """)
    # end test_primary_key1
        
    def test_primary_key2(self):
        """Check that PKs are enforced"""

        self.db.execute("""
        CREATE TABLE nosetest1 (
        field1	INT	NOT NULL
                CONSTRAINT nosetest1_pk PRIMARY KEY,
        field2	INT	NOT NULL
        )
        """)

        insert1 = """
        INSERT INTO [:table schema=cerebrum name=nosetest1]
        (field1, field2)
        VALUES (1, 2)
        """

        self.db.execute(insert1)
        assert_raises(self.db.DatabaseError,
                      self.db.execute,
                      insert1)
    # end test_primary_key2


    def test_foreign_key1(self):
        """Check that foreign keys can be created"""

        self.db.execute("""
        CREATE TABLE nosetest1 (
        field1	INT	NOT NULL
                CONSTRAINT nosetest1_pk PRIMARY KEY
        )
        """)

        self.db.execute("""
        CREATE TABLE nosetest2 (
        field1 INT NOT NULL,
        CONSTRAINT nosetest2_fk
        FOREIGN KEY (field1)
        REFERENCES nosetest1(field1)
        )
        """)
    # end test_foreign_key1

    def test_foreign_key2(self):
        """Check that foreign keys are enforced"""

        self.db.execute("""
        CREATE TABLE nosetest1 (
        field1	INT	NOT NULL
                CONSTRAINT nosetest1_pk PRIMARY KEY
        )
        """)

        self.db.execute("""
        CREATE TABLE nosetest2 (
        field1 INT NOT NULL,
        CONSTRAINT nosetest2_fk
        FOREIGN KEY (field1)
        REFERENCES nosetest1(field1)
        )
        """)

        insert1 = """
        INSERT INTO [:table schema=cerebrum name=nosetest1] (field1)
        VALUES (1)
        """
        insert2 = """
        INSERT INTO [:table schema=cerebrum name=nosetest2] (field1)
        VALUES (1)
        """

        # fail, when the value is not in the referred table
        assert_raises(self.db.DatabaseError,
                      self.db.execute,
                      insert2)
    # end test_foreign_key2

    def test_foreign_key3(self):
        """Check that foreign keys are observed"""

        self.db.execute("""
        CREATE TABLE nosetest1 (
        field1	INT	NOT NULL
                CONSTRAINT nosetest1_pk PRIMARY KEY
        )
        """)

        self.db.execute("""
        CREATE TABLE nosetest2 (
        field1 INT NOT NULL,
        CONSTRAINT nosetest2_fk
        FOREIGN KEY (field1)
        REFERENCES nosetest1(field1)
        )
        """)

        insert1 = """
        INSERT INTO [:table schema=cerebrum name=nosetest1] (field1)
        VALUES (1)
        """
        insert2 = """
        INSERT INTO [:table schema=cerebrum name=nosetest2] (field1)
        VALUES (1)
        """

        # this always succeeds
        self.db.execute(insert1)

        # this must succeed now
        self.db.execute(insert2)
    # end test_foreign_key2


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


    def test_support_Norwegian_chars(self):
        """Make sure we can use Norwegian chars"""

        # FIXME: Fuck! naming parameters *requires* cereconf, a database and a
        # bunch of constants. This is silly.
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
        
        
    def test_datetime(self):
        """Insert/delete datetime values"""

        self.db.execute("""
        CREATE TABLE nosetest1 (
        field1  INT	NOT NULL,
        field2	DATE	NOT NULL DEFAULT [:now]
        )
        """)

        # self.db.execute("""
        # INSERT INTO [:table schema=cerebrum name=nosetest1] (field1, field2)
        # VALUES ()
        # 
        # """)
    # end test_datetime
        

    def test_boolean(self):
        """Insert/delete bool values"""
        pass

    def test_union_of_numeric(self):
        """SELECT ... UNION of 2 numeric(x, 0) must return int"""
        pass

    def test_extraneous_bind_parameters(self):
        """Check that free variables substitution copes with extraneous names"""

        # Oracle does not like this
        pass

    def test_free_variables(self):
        """Check that :name placeholders work"""

        # This one is actually *VERY* important
        
# end DBTestBase
