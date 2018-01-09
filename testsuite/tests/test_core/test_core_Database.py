#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory

import Cerebrum.database
from functools import wraps

from nose.tools import raises, assert_raises


# TODO: This could be done better...

def create_table(table_name, *table_defs):
    """ Decorator for tests that creates a temporary tables.

    This method creates the actual decorator, based on the arguments given.
    The wrapped method must take a database connection as first argument, and
    the table_name as the second argument.

    @type table_name: str
    @param table_name: The name of the temporary table

    @type table_defs: *tuple
    @param table_defs: Variable length arguments, each is a string that defines
        a column in the table

    @rtype: decorator
    @return: A decorator that can be used to wrap a test function

    """

    def wrap(method):
        """ This is the I{actual} decorator. It returns a wrapped C{method}.

        The decorated method will create a database object, use it to create a
        new table. The table name and db connection will be passed on to the
        wrapped method as the first and second argument, respectively.

        After the method returns, we perform a rollback on the transaction.
        """
        # The 'wraps' decorator sets up proper __doc__ and __name__ attrs
        @wraps(method)
        def wrapper(db, *args, **kwargs):
            """ See help L{%s} for info""" % method.__name__

            assert isinstance(db, Cerebrum.database.Database)
            db.execute('create table %s (%s)' % (
                table_name, ','.join(table_defs)))
            method(db, table_name, *args, **kwargs)

        return wrapper
    return wrap


def use_db(commit=False, **db_args):
    """ Wrap a function to provide and perform rollback on database object.

    The decorated method will create a database object, and pass it on as
    the first argument to the wrapped function. After the wrapped function
    returns, we perform a rollback on the transaction.

    @type db_args: dict
    @param db_args: Keyword-arguments for the database constructor

    @rtype: decorator
    @return: A decorator that can be used to wrap a test function

    """

    def wrap(method):
        """ Wrap a function to provide and perform rollback on database object.

        The decorated method will create a database object, and pass it on as
        the first argument to the wrapped function. After the wrapped function
        returns, we perform a rollback on the transaction.

        """
        # The 'wraps' decorator sets up proper __doc__ and __name__ attrs
        @wraps(method)
        def wrapper(*args, **kwargs):
            """ See help L{%s} for info""" % method.__name__
            try:
                db = Factory.get('Database')(**db_args)
                if not commit:
                    db.commit = db.rollback
                method(db, *args, **kwargs)
            finally:
                db.rollback()
        return wrapper
    return wrap


@use_db()
@create_table('foo', 'x int not null')
def test_rollback(db, table_name):
    """ Database.rollback() transaction rollback functionality. """
    insert_sql = 'insert into %s(%s) values (:value)' % (table_name, 'x')
    select_sql = 'select %s from %s' % ('x', table_name)

    for value in (0, 1, 2, 3):
        db.execute(insert_sql, {'value': value})

    res = db.query(select_sql)
    assert len(res) > 0

    db.rollback()

    # Only this should generate DatabaseError
    try:
        db.query(select_sql)
    except Cerebrum.database.DatabaseError, e:
        # Note that this test will break if the exception doesn't have an sql
        # attr.
        assert e.operation == repr(select_sql)
    else:
        # Should raise error
        assert False, 'No error raised'


def test_commit():
    """ Database.commit() transaction commit functionality. """

    # We use two instantiations of Database, each one should have their own
    # transaction, and one should not be able to see the effects of the other,
    # before commit() is performed.
    db_cls = Factory.get('Database')
    table_name = 'foo'

    create_sql = 'create table %s (%s int not null)' % (table_name, 'x')
    select_sql = 'select %s from %s' % ('x', table_name)
    drop_sql = 'drop table %s' % table_name

    # NOTE: We use postgres-specific functonality here.
    #       This may not work if we switch drivers, and will almost certainly
    #       break if we use anything but postgres.
    # TODO/TBD - maybe we should wrap all our stuff in this, so that we can
    #            commit/rollback in our other methods as well?
    db = db_cls()
    db.execute(create_sql)
    try:
        db.commit()
        db.close()
        db = db_cls()
        # Create table and data in db1
        db.query(select_sql)
    finally:
        db.close()
        db = db_cls()
        db.execute(drop_sql)
        db.commit()


@use_db()
@create_table('foo', 'x int not null')
def test_db_simple_query(db, table_name):
    """ Database.execute() database basics. """

    insert_sql = 'insert into %s(%s) values (:value)' % (table_name, 'x')
    select_sql = 'select count(*) as one from %s' % table_name

    lo, hi = 1, 4
    for x in range(lo, hi):
        db.execute(insert_sql, {'value': x})
    count = db.query_1(select_sql)
    assert count == hi - lo


@use_db()
@create_table('foo', 'x int not null', 'y int null')
def test_db_numeric_interaction(db, table_name):
    """ Database.execute() numeric processing by the backend. """

    insert_sql = 'insert into %s(%s) values (:value)' % (table_name, 'x')
    select_sql = 'select * from %s where %s = :value' % (table_name, 'x')

    values = (0, 1, -10, 10, 2**30, -2**30)

    for value in values:
        db.execute(insert_sql, {'value': value})

    for value in values:
        row = db.query_1(select_sql, {'value': value})
        #assert type(row['x']) is type(value) # int -> long, for any numerical
        assert row['x'] == value


@use_db(client_encoding='utf-8')
@create_table('foo', 'x text not null', 'y integer null')
def test_db_unicode_interaction(db, table_name):
    """ Database.execute() unicode text. """

    insert_sql = 'insert into %s(%s) values (:value)' % (table_name, 'x')
    select_sql = 'select * from %s where %s = :value' % (table_name, 'x')

    # TODO: What about "øæå"? Should the backend somehow guess the
    # encoding? Or assume some default? Or read it from cereconf?

    values = (u'unicode', u'latin-1:øåæ', unicode('utf-8:øæå', 'utf-8'))

    for value in values:
        db.execute(insert_sql, {"value": value})

    for value in values:
        row = db.query_1(select_sql, {"value": value})
        retval = row['x']
        if type(retval) is not unicode:
            retval = unicode(retval, 'utf-8')
        assert retval == value


def test_db_exception_types():
    """ Database.Error, correct class types. """

    # We can't wrap methods that yield other functions.
    db = Factory.get('Database')()

    tests = [
        (Cerebrum.database.Error, db.IntegrityError(
            'Database error is not instance of Cerebrum.database.Error')),
        (Cerebrum.database.Warning, db.Warning(
            'Database warning is not instance of Cerebrum.database.Warning')),
        (db.Error, db.IntegrityError(
            'Database error is not instance of self.Error')), ]

    # We can't wrap a statement...
    def raise_exception(e):
        """ Raise a given exception. """
        raise e

    for catch_with, throw in tests:
        func = raises(catch_with)(raise_exception)
        yield func, throw


@use_db()
def test_exception_catch_base(db):
    """ Catch exception raised by the db-driver with Database.Error. """
    assert_raises(Cerebrum.database.Error,
                  db.execute,
                  "create table foo")


@use_db()
def test_exception_catch_instance(db):
    """ Catch exception raised by the db-driver with db.Error. """
    assert_raises(db.Error,
                  db.execute,
                  "create table foo")


@use_db()
@create_table('foo', 'x int not null', 'y int null')
@create_table('bar', 'z int not null', 'y text null')
def test_unions_with_numeric(db, bar_name, foo_name):
    """ Database.execute(), SQL UNION on numericals returns int/long. """
    foo_insert = 'insert into %s values (:x, :y)' % foo_name
    bar_insert = 'insert into %s values (:z, :y)' % bar_name
    select_sql = 'select %s as n from %s union select %s as n from %s' % (
        'x', foo_name, 'z', bar_name)

    db.execute(foo_insert, {'x': 1, 'y': 2})
    db.execute(bar_insert, {'z': 3, 'y': 'bar'})
    resultset = db.query(select_sql)

    assert len(resultset) == 2
    for row in resultset:
        assert isinstance(row['n'], (int, long))


@use_db()
def test_all_critical_db_attributes(db):
    """ Database attributes. """

    # - Make sure that Factory.get('Database')() always has a _db, _cursor and
    # the like. Both after the *first* and after the *n'th* call.

    assert hasattr(db, "_db")
    assert hasattr(db, "_cursor")
    # WTF else do we need?


#@raises(Exception)
#@use_db()
#@create_table('foo', 'x int not null')
#def test_select_count(db, table_name):
    #""" Check that select(*) is named.

    #We do not allow nameless select(*) in our code, since the db-row class
    #will try to somehow dub the attribute corresponding to 'count(*)' of a
    #'select count(*) from ...' clause. Not sure what kind of exceptions is
    #thrown at us, though.

    #"""
    #db.query("select count(*) from %s" % table_name)


#def test_check_query_1():
    #""" Check that query_1(<one attr>) gives that attr"""

    #pass


@raises(Cerebrum.database.ProgrammingError)
@use_db()
@create_table('foo', 'x int not null', 'y int null')
def test_multiple_queries(db, foo_name):
    """ Database.execute(), multiple queries are forbidden. """
    foo_select = 'select * from %s' % foo_name
    db.execute(';'.join((foo_select, foo_select)))


@raises(Cerebrum.database.ProgrammingError)
@use_db()
def test_missing_table(db):
    """ Database.ProgrammingError for non-existing relation. """
    foo_select = 'select * from efotdzzb'
    db.execute(foo_select)
