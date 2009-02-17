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
  entire transaction will be aborted! (and the succeeding test will fail
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
import mx.DateTime

from nose.tools import assert_raises, assert_almost_equals



def sneaky_import(name, with_debug=False):
    """Import module L{name}, falling back to 'relative' import from the
    Cerebrum installation where *this* file is located.

    @type
    
    """
    import cereconf
    
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

    # Database.py wants CoreConstants to remap named placeholders to
    # keys. CoreConstants wants this dictionary. If we fix it here, there'll
    # be one less thing to think about.
    if not hasattr(cereconf, "ENTITY_TYPE_NAMESPACE"):
        cereconf.ENTITY_TYPE_NAMESPACE = {
             'account': 'account_names',
             'dns_owner': 'dns_owner_ns',
             'group': 'group_names',
             'host': 'host_names'
        }

    if with_debug:
        sys.stdout.flush()
        print "\nImported <%s> from %s" % (name, mod.__file__)
        sys.stdout.flush()

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
        # If a backend needs a schema, this has to be overridden in the
        # subclass. Those that do not want/need this, can simply leave this
        # default.
        self.schema = "cerebrum"
    # end __init__


    def _get_table(self, name):
        """Return a backend-specific name for a table.

        This method should be used for all tests, since some backends have a
        peculiar way of addressing tables. E.g. oracle uses a schema name (in
        some situations) to refer to an entity (table, sequence, etc)

        @type name: basestring
        @param name: plain table name.
        """

        if hasattr(self, "schema") and self.schema:
            return "[:table name=%s schema=%s]" % (name, self.schema)
        return name
    # end _get_table


    def setup(self):
        raise NotImplementedError("You must implement setup() "
                                  "for your db-backend")
    # end setup


    def teardown(self):
        raise NotImplementedError("You must implement teardown() "
                                  "for your db-backend")
    # end teardown


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
        field1	char varying(10)
        )""")
    # end test_table_create1


    def test_table_all_datatypes(self):
        """Create a table with all used data types"""

        self.db.execute("""
        CREATE TABLE nosetest1 (
            field1	CHAR VARYING (10),
            field2	CHAR(20),
            field3	NUMERIC(12, 0),
            field4	DATE,
            field5      TIMESTAMP
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
        INSERT INTO %s
        (field1, field2)
        VALUES ([:now], 20)
        """ % self._get_table("nosetest1"))

        self.db.query("""
        SELECT *
        FROM %s
        WHERE field1 = [:now]
        """ % self._get_table("nosetest1"))
    # end test_cerebrum_syntax


    def test_cerebrum_syntax_now_is_sensible(self):
        """Check that [:now] returns a value close to now"""

        self.db.execute("""
        CREATE TABLE nosetest1 (
        field1	DATE NOT NULL,
        field2  INT NULL
        )
        """)

        self.db.execute("""
        INSERT INTO %s (field1)
        VALUES ([:now])
        """% self._get_table("nosetest1"))

        value = self.db.query_1("""
        SELECT * FROM %s""" % self._get_table("nosetest1"))

        now = mx.DateTime.now()
        diff = (now - value["field1"])
        assert diff < mx.DateTime.DateTimeDelta(1) # less than 1 day
    # end test_cerebrum_syntax_now_is_sensible


    def test_query_1_from_single_is_not_dbrow(self):
        """Check that query_1() on a single column returns that value only

        query_1('select field1 from ...') should return field1 only (and not
        the db_row type with that column). This is how we've defined the
        semantics of query_1().
        """

        self.db.execute("""
        CREATE TABLE nosetest1 (
        field1	CHAR VARYING (10) NOT NULL
        )
        """)

        value = "message"
        self.db.execute("INSERT INTO %s VALUES (:value)" %
                        self._get_table("nosetest1"),
                        {"value": value})

        db_value = self.db.query_1("""
        SELECT field1 FROM %s
        WHERE field1 = :value""" % self._get_table("nosetest1"),
                                   {"value": value})

        assert db_value == value
    # end test_query_1_from_single_is_not_dbrow


    def test_python_date_to_db(self):
        """Check that mx.DateTime can be stored """

        self.db.execute("""
        CREATE TABLE nosetest1 (
        field1 DATE NOT NULL
        )
        """)

        self.db.execute("INSERT INTO %s VALUES (:value)" %
                        self._get_table("nosetest1"),
                        {"value": mx.DateTime.now()})
    # end test_python_date_to_db


    def test_date_delete(self):
        """Insert/delete into DATE row type"""

        self.db.execute("""
        CREATE TABLE nosetest1 (
        field1  INT	NOT NULL,
        field2	DATE	DEFAULT [:now] NOT NULL 
        )
        """)

        now = mx.DateTime.now()
        self.db.execute("""
        INSERT INTO %s (field1, field2) VALUES (1, :value)
        """ % self._get_table("nosetest1"), {"value": now})

        self.db.execute("DELETE FROM %s WHERE field2 = :value" %
                        self._get_table("nosetest1"),
                        {"value": now})

        # we cannot have any rows
        assert not self.db.query("SELECT * from %s" %
                                 self._get_table("nosetest1"))
    # end test_date_delete


    def test_mxdatetime_to_timestamp(self):
        """Check that mx.DateTime dates can be stored in the db"""

        self.db.execute("""
        CREATE TABLE nosetest1 (
        field1 TIMESTAMP NOT NULL
        )
        """)

        self.db.execute("INSERT INTO %s VALUES (:value)" %
                        self._get_table("nosetest1"),
                        {"value": mx.DateTime.now()})
    # end test_mxdatetime_to_timestamp


    def test_timestamp_delete(self):
        """Insert/delete into TIMESTAMP row type"""

        self.db.execute("""
        CREATE TABLE nosetest1 (
        field1  INT		NOT NULL,
        field2	TIMESTAMP 	DEFAULT [:now] NOT NULL 
        )
        """)

        now = mx.DateTime.now()
        self.db.execute("INSERT INTO %s (field1, field2) VALUES (1, :value)" %
                        self._get_table("nosetest1"),
                        {"value": now})

        self.db.execute("DELETE FROM %s WHERE field2 = :value" %
                        self._get_table("nosetest1"), 
                        {"value": now})

        # we cannot have any rows
        assert not self.db.query("SELECT * FROM %s" % self._get_table("nosetest1"))
    # end test_date_delete


    def test_date_maps_to_mxdatetime(self):
        """SELECT a DATE -> mx.DateTime.DateTimeType"""

        self.db.execute("""
        CREATE TABLE nosetest1 (
        field1	DATE DEFAULT [:now] NOT NULL 
        )
        """)

        now = mx.DateTime.now()
        self.db.execute("INSERT INTO %s (field1) VALUES (:value)" %
                        self._get_table("nosetest1"), 
                        {"value": now})

        rows = self.db.query("SELECT * FROM %s" %
                             self._get_table("nosetest1"))
        assert len(rows) == 1
        row = rows[0]
        assert type(row["field1"]) is mx.DateTime.DateTimeType
    # end test_date_maps_to_mxdatetime


    def test_timestamp_maps_to_mxdatetime(self):
        """SELECT a TIMESTAMP -> mx.DateTime.DateTimeType"""

        self.db.execute("""
        CREATE TABLE nosetest1 (
        field1	TIMESTAMP DEFAULT [:now] NOT NULL
        )
        """)

        now = mx.DateTime.now()
        self.db.execute("INSERT INTO %s (field1) VALUES (:value)" %
                        self._get_table("nosetest1"), 
                        {"value": now})

        rows = self.db.query("SELECT * FROM %s" % self._get_table("nosetest1"))
        assert len(rows) == 1
        row = rows[0]
        assert type(row["field1"]) is mx.DateTime.DateTimeType
    # end test_timestamp_maps_to_mxdatetime


    def test_cerebrum_syntax_table(self):
        """Check Cerebrum's [:table] syntax extension"""

        # If we have not defined a schema, there is no point in running this
        # test. Is silent success ok in this case?
        if not self.schema:
            return 

        self.db.query("""
        CREATE TABLE nosetest1 (
        field1	INT,
        field2  INT
        )
        """)

        self.db.query("SELECT * FROM %s" % self._get_table("nosetest1"))
        self.db.execute("INSERT INTO %s (field1, field2) VALUES (1, 2)" %
                        self._get_table("nosetest1"))
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
        assert y == start
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

        insert1 = ("INSERT INTO %s (field1, field2) VALUES (1, 2)" %
                   self._get_table("nosetest1"))

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

        # This is the insert that should have been in nosetest1
        # insert1 = ("INSERT INTO %s (field1) VALUES (1)" %
        #            self._get_table("nosetest1"))

        insert2 = ("INSERT INTO %s (field1) VALUES (1)" %
                   self._get_table("nosetest2"))

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

        insert = "INSERT INTO %s (field1) VALUES (1)" 

        # this always succeeds
        self.db.execute(insert % self._get_table("nosetest1"))

        # this must succeed now
        self.db.execute(insert % self._get_table("nosetest2"))
    # end test_foreign_key2


    def test_union_of_numeric(self):
        """SELECT ... UNION of 2 numeric(x, 0) must return int

        We had issues with DCOracle2 and this test case.
        """

        self.db.execute("""
        CREATE TABLE nosetest1 (
        field1 NUMERIC(6, 0) NOT NULL
        )
        """)

        self.db.execute("""
        CREATE TABLE nosetest2 (
        field2 NUMERIC(6, 0) NOT NULL
        )
        """)

        self.db.execute("INSERT INTO %s (field1) VALUES (1)" %
                        self._get_table("nosetest1"))

        self.db.execute("INSERT INTO %s (field2) VALUES (2)" %
                        self._get_table("nosetest2"))

        result = self.db.query("""
        SELECT field1 as field FROM %s
        UNION
        SELECT field2 as field FROM %s
        """ % (self._get_table("nosetest1"), self._get_table("nosetest2")))

        assert len(result) == 2
        for x in result:
            assert isinstance(x["field"], (int, long))
    # end test_union_of_numeric


    def test_extraneous_bind_parameters(self):
        """Check that free variables substitution copes with extraneous names

        We had issues with DCOracle2 and this test case.
        """

        self.db.execute("""
        CREATE TABLE nosetest1(
        field1 NUMERIC(6, 0) NOT NULL
        )
        """)

        self.db.execute("INSERT INTO %s (field1) VALUES (:value1)" %
                        self._get_table("nosetest1"),
                        {"value1": 10, "value2": None,})

        x = self.db.query_1("SELECT field1 FROM %s WHERE field1 = :value1" %
                            self._get_table("nosetest1"),
                            {"value1": 10, "value2": None,})
        assert x == 10
    # end test_extraneous_bind_parameters
    

    def test_all_args_must_be_named(self):
        """Make sure that unnamed columns in select are tripped on"""

        self.db.execute("""
        CREATE TABLE nosetest1(
        field1 NUMERIC(6, 0) NOT NULL
        )
        """)
        
        self.db.execute("INSERT INTO %s (field1) VALUES (1)" %
                        self._get_table("nosetest1"))

        # NB! select count(*) from nosetest1 actually works. Why?
        assert_raises(Exception,
                      self.db.query,
                      "SELECT 1, count(*) FROM %s" % self._get_table("nosetest1"))
    # end test_all_args_must_be_named


    def test_unnamed_asterix(self):
        """Check that SELECT * works"""

        self.db.execute("""
        CREATE TABLE nosetest1(
        field1 NUMERIC(6, 0) NOT NULL,
        field2 NUMERIC(6, 0) NOT NULL
        )
        """)

        self.db.execute("INSERT INTO %s VALUES (1, 2)" %
                        self._get_table("nosetest1"))

        row = self.db.query_1("SELECT * FROM %s" % self._get_table("nosetest1"))

        # they weren't named explicitly, but we can still access them
        assert row["field1"] == 1
        assert row["field2"] == 2
    # end test_unnamed_asterix


    def test_named_aggregates_are_accepted(self):
        """Make sure 'func() as name' is accepted"""

        self.db.execute("""
        CREATE TABLE nosetest1(
        field1 NUMERIC(6, 0) NOT NULL
        )
        """)

        items = range(5)
        for item in items:
            self.db.execute("INSERT INTO %s (field1) VALUES (%d)""" %
                            (self._get_table("nosetest1"), item))

        x = self.db.query_1("SELECT SUM(field1) AS total FROM %s" %
                            self._get_table("nosetest1"))
        assert x == sum(items)
    # end test_named_aggregates_are_accepted


    def test_process_none(self):
        """Check that None <-> NULL works

        None should be stored transparently as NULL. NULL should be
        transparently converted to None.
        """

        self.db.execute("""
        CREATE TABLE nosetest1(
        field1 NUMERIC(6, 0) NULL
        )
        """)

        self.db.execute("INSERT INTO %s (field1) VALUES (:value)" %
                        self._get_table("nosetest1"),
                        {"value": None})

        x = self.db.query_1("SELECT field1 FROM %s" %
                            self._get_table("nosetest1"))
        assert x is None
    # end test_process_none


    def test_query_1_fails_on_many(self):
        """query_1() cannot return more than 1 row"""

        self.db.execute("""
        CREATE TABLE nosetest1(
        field1 NUMERIC(6, 0) NULL
        )
        """)

        items = range(5)
        for item in items:
            self.db.execute("INSERT INTO %s (field1) VALUES (%d)" %
                            (self._get_table("nosetest1"), item))

        assert_raises(Exception,
                      self.db.query_1,
                      "SELECT * FROM %s" % self._get_table("nosetest1"))
    # end test_query_1_fails_on_many

    def test_query_1_cannot_returns_0(self):
        """Check that query_1() cannot return 0 rows"""

        self.db.execute("""
        CREATE TABLE nosetest1(
        field1 NUMERIC(6, 0) NULL
        )
        """)

        assert_raises(Exception,
                      self.db.query_1,
                      "SELECT * FROM %s" % self._get_table("nosetest1"))
    # end test_query_1_returns_0


    def test_free_variables(self):
        """Check that :name placeholders work

        This one is *VERY* important.
        """

        self.db.execute("""
        CREATE TABLE nosetest1(
        field1 NUMERIC(6, 0) NULL
        )
        """)

        x = 1
        self.db.execute("INSERT INTO %s (field1) VALUES (:value)" %
                        self._get_table("nosetest1"),
                        {"value": x})

        row = self.db.query_1("SELECT * FROM %s WHERE field1 = :value" %
                              self._get_table("nosetest1"), {"value": x})
        assert row
    # end test_free_variables


    def test_numeric0_gives_int(self):
        """Check that NUMERIC(X, 0) operates on int/long.

        Fetching from NUMERIC(X, 0) *must* return us an int/long.
        """

        self.db.execute("""
        CREATE TABLE nosetest1(
        field1 NUMERIC(6, 0) NOT NULL
        )
        """)

        x = 1
        self.db.execute("INSERT INTO %s (field1) VALUES (:value)" %
                        self._get_table("nosetest1"), {"value": x})

        rows = self.db.query("SELECT * FROM %s" % self._get_table("nosetest1"))
        assert len(rows) == 1
        row = rows[0]
        assert isinstance(row["field1"], (int, long))
    # end test_numeric0_gives_int
        

    def test_insert_unicode1(self):
        """Check that we can send unicode to CHAR/VARCHAR/TEXT"""

        # latin-1
        text = "blåbærsyltetøy" 
        utext = unicode(text, "latin-1")

        self.db.execute("""
        CREATE TABLE nosetest1(
        field1 VARCHAR(50) NOT NULL
        )
        """)

        self.db.execute("INSERT INTO %s (field1) VALUES (:value)" %
                        self._get_table("nosetest1"),
                        {"value": utext})
    # end test_insert_unicode


    def test_retrieve_unicode1(self):
        """Check that we fish out unicode objects from CHAR/VARCHAR/TEXT"""

        # latin-1
        text = "blåbærsyltetøy" 
        utext = unicode(text, "latin-1")

        self.db.execute("""
        CREATE TABLE nosetest1(
        field1 VARCHAR(50) NOT NULL
        )
        """)

        self.db.execute("INSERT INTO %s (field1) VALUES (:value)" %
                        self._get_table("nosetest1"),
                        {"value": utext})
        rows = self.db.query("SELECT * FROM %s" % self._get_table("nosetest1"))
        assert rows[0]["field1"] == utext
        assert type(rows[0]["field1"]) == type(utext)
    # end test_insert_unicode


    def test_check_decimal1(self):
        """Check that we mask Decimal.

        We should check whether there are situations when the backend returns
        a Decimal. Our code is NOT prepared for this.
        """

        self.db.execute("""
        CREATE TABLE nosetest1(
        field1  NUMERIC(7, 2)   NOT NULL
        )
        """)

        x = 12.56
        self.db.execute("INSERT INTO %s (field1) VALUES (:x)" %
                        self._get_table("nosetest1"),
                        locals())
        value = self.db.query_1("SELECT * from %s" % self._get_table("nosetest1"))
        assert isinstance(value, float)
        assert_almost_equals(value, x, places=2)
    # end test_check_decimal
        
        
# end DBTestBase
