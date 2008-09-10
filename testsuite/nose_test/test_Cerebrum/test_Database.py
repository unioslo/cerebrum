#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""Testing of Database.py's functionality

- Make sure that Factory.get('Database')() always has a _db, _cursor and the
  like. Both after the *first* and after the *n'th* call.

- For *all* string-like attributes in the db (yeah, it's a lot), assert that
  whatever is fed into the db, is fetched back properly in the presence of
  different encodings.

- Test threading/fork()ing

- Test constant insertion and deletion

- Testing 'our' sql-lexer extensions should be put in its own file
  (test_sql_lexer or somesuch)
"""

import sys
import cerebrum_path, cereconf
from Cerebrum.Utils import Factory
import Cerebrum.Database

from nose.tools import raises, assert_raises


def with_tmp_table(func, table_def, tables_to_drop):
    def test_wrapper(*rest, **kw_args):
        try:
            db = Factory.get("Factory")()
            db.execute(table_def)
        finally:
            for tname in tables_to_drop:
                db.execute("drop table " + tname)
            db.rollback()
    # test_wrapper

    # FIXME FIXME FIXME FIXME: this crap is not done
# end with_tmp_table


def test_db_simple_query():
    """Test db basics"""

    try:
        db = Factory.get("Database")()
        db.execute("create table foo ( x int not null )")
        lo, hi = 1, 4
        for x in range(lo, hi):
            db.execute("insert into foo values (%d)" % x)

        result = db.query_1("select count(*) as one from foo")
        assert result == hi - lo
    finally:
        db.execute("drop table foo")
        db.rollback()
# end test_db_simple_query


def test_db_numeric_interaction():
    """Test numeric processing by the backend"""
    
    try:
        db = Factory.get("Database")()
        db.execute("create table foo ( x integer not null, y integer null )")
        # How does the db respond to number storage?
        values = (0, 1, sys.maxint, -1, -sys.maxint, sys.maxint*10,
                  -sys.maxint*10)
        for value in values:
            db.execute("insert into foo(x) values (:value)",
                       {"value": value})

        # Now, can we fetch the same values? If so, what's their type?
        for value in values:
            row = db.query_1("select * from foo where x = :value",
                             {"value": value})
            assert type(row["x"]) is type(value)
            assert row["x"] == value
    finally:
        db.execute("drop table foo")
        db.rollback()
# end test_db_numeric_interaction


def test_db_unicode_interaction():
    """Test unicode """

    try:
        db = Factory.get("Database")()
        db.execute("create table foo (x text not null, y interger null)")

        # TODO: What about "øæå"? Should the backend somehow guess the
        # encoding? Or assume some default? Or read it from cereconf?
        
        values = ('ascii', u'unicode', u'latin-1:øåæ',
                  unicode("utf-8:øæå", "utf-8"))
        for value in values:
            db.execute("insert into foo(x) values (:value)",
                       {"value": value})

        for value in values:
            row = db.query_1("select * from foo where x = :value",
                             {"value": value})
            # all backends should return unicode *only*
            assert type(row["x"]) is unicode
            if type(value) is not unicode:
                assert row["x"] == unicode(value, "utf-8")
            else:
                assert row["x"] == value
    finally:
        db.execute("drop table foo")
        db.rollback()
# end test_db_unicode_interaction


@raises(Cerebrum.Database.Error)
def test_working_errors1():
    """Check that db Errors are sane."""

    db = Factory.get("Database")()
    raise db.IntegrityError("fuckit")
# end test_working_errors1


@raises(Cerebrum.Database.Error)
def test_working_errors2():
    """Check that something._db.Errors are sane."""

    g = Factory.get("Group")(Factory.get("Database")())
    raise g._db.IntegrityError("fuckit")
# end test_working_errors


@raises(Cerebrum.Database.Warning)
def test_working_warnings1():
    """Check that db.Warnings are sane."""

    db = Factory.get("Database")()
    raise db.Warning("fuckit")
# end test_working_warnings


@raises(Cerebrum.Database.Warning)
def test_working_warnings2():
    """Check that something._db.Warnings are sane."""

    db = Factory.get("Database")()
    g = Factory.get("Group")(db)
    raise g._db.Warning("fuckit")
# end test_working_warnings2
    

def test_sane_error_hierarchy():
    """Check that exception hierarchy will work with >=2.5."""

    db = Factory.get("Database")()
    assert_raises(Cerebrum.Database.Error,
                  db.execute,
                  "create table foo")
# end test_sane_error_hierarchy        


def test_unions_with_numeric():
    """Check that SQL UNION on ints gives an int.
    
    Some (?) oracle backends fail at this one.
    """

    db = Factory.get("Database")()
    # make a decorator for this try-finally block?
    try:
        db.execute("create table foo ( x integer not null, y integer null )")
        db.execute("create table bar ( z integer not null, y text null )")
        db.execute("insert into foo values (1, 2)")
        db.execute("insert into bar values (3, 'bar')")

        resultset = db.query("select x as name from foo union select z as name from bar")
        assert len(resultset) == 2
        for row in resultset:
            assert isinstance(row["name"], int)
    finally:
        db.execute("drop table bar")
        db.execute("drop table foo")
        db.rollback()
# end test_unions_with_numeric


def test_all_critical_db_attributes():
    """Check that all interesting db members are here."""

    # - Make sure that Factory.get('Database')() always has a _db, _cursor and the
    # like. Both after the *first* and after the *n'th* call.

    db = Factory.get("Database")()
    assert hasattr(db, "_db")
    assert hasattr(db, "_cursor")
    # WTF else do we need?
# end test_all_critical_db_attributes


@raises(Exception)
def test_select_count():
    """Check that select(*) is named.

    We do not allow nameless select(*) in our code, since the db-row class
    will try to somehow dub the attribute corresponding to 'count(*)' of a
    'select count(*) from ...' clause. Not sure what kind of exceptions is
    thrown at us, though.
    """

    try:
        db = Factory.get("Database")()
        db.execute("create table foo (x int not null)")
        db.query("select count(*) from foo")
    finally:
        db.execute("drop table foo")
        db.rollback()
# end test_select_count


def test_check_query_1():
    """Check that query_1(<one attr>) gives that attr"""

    pass
        
