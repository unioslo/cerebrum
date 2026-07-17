# -*- coding: utf-8 -*-
"""
Tests for :mod:`Cerebrum.database`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import pytest
import six

from Cerebrum import Errors
from Cerebrum.Utils import Factory
import Cerebrum.database


#
# Common fixtures and helpers
#


def create_table(db, table_name, *table_defs):
    """
    Create a table.

    :param str table_name: The name of the temporary table
    :param str *: column definitions
    """
    db.execute('create table %s (%s)' % (table_name, ','.join(table_defs)))
    return table_name


@pytest.fixture
def db_cls():
    return Factory.get('Database')


@pytest.fixture
def db(db_cls):
    try:
        database = db_cls()
        database.commit = database.rollback
        yield database
    finally:
        # In case we've closed the db connection already
        if database._db:
            database.rollback()


class _Table(object):
    """ Helper to create table and insert rows. """

    def __init__(self, name, **cols):
        self.name = name
        self.cols = cols

    @property
    def create(self):
        return 'create table {table}({cols})'.format(
            table=self.name,
            cols=', '.join(('{} {}'.format(k, v)
                            for k, v in self.cols.items())),
        )

    def fmt_insert(self, **values):
        cols = list(sorted(values))
        stmt = 'insert into {table}({cols}) values ({vals})'.format(
            table=self.name,
            cols=', '.join(cols),
            vals=', '.join((':' + col for col in cols)),
        )
        return stmt, values

    def insert(self, db, **values):
        stmt, binds = self.fmt_insert(**values)
        db.execute(stmt, binds)


@pytest.fixture
def table_foo_x(db):
    """ create table with columns: x (int). """
    t = _Table('foo', x='int not null')
    db.execute(t.create)
    return t


@pytest.fixture
def table_foo_xy(db):
    """ create table with columns: x (int), y (int, null). """
    t = _Table('foo', x='int not null', y='int null')
    db.execute(t.create)
    return t


@pytest.fixture
def table_bar_xy(db):
    """ create table with columns: x (text), y (int, null). """
    t = _Table('bar', x='text not null', y='int null')
    db.execute(t.create)
    return t


@pytest.fixture
def table_baz_zy(db):
    """ create table with columns: z (int), y (text, null). """
    t = _Table('baz', z='int not null', y='text null')
    db.execute(t.create)
    return t


@pytest.fixture
def table_text(db):
    """ create table with columns: value (text, null). """
    t = _Table('text', value='text null')
    db.execute(t.create)
    return t


@pytest.fixture
def sequence(db):
    name = "test_sequence"
    start = 1
    db.execute(
        """
        create temporary sequence {} as int
        start {}
        """.format(name, start)
    )
    return name, start


#
# _pretty_sql() tests
#


def test_pretty_sql():
    assert Cerebrum.database._pretty_sql(
        """
        SELECT * from foo
        WHERE bar=:baz
        """
    ) == "SELECT * from foo WHERE bar=:baz"


def test_pretty_sql_maxlen():
    assert Cerebrum.database._pretty_sql(
        """
        SELECT * from foo
        WHERE bar=:baz
        """,
        maxlen=10,
    ) == "SELECT * f..."


#
# database basics
#


def test_db_ping(db):
    db.ping()
    assert True


def test_abstract_db_init():
    with pytest.raises(NotImplementedError) as exc_info:
        Cerebrum.database.Database()
    error_msg = six.text_type(exc_info.value)
    assert "abstract class" in error_msg


def test_db_reconnect_open(db):
    with pytest.raises(Cerebrum.database.Error) as exc_info:
        db.connect()
    error_msg = six.text_type(exc_info.value)
    assert "connection already open" in error_msg


def test_db_close(db):
    real_db = db.driver_connection()
    cursor = db._cursor
    real_cursor = cursor.driver_cursor()
    db.close()

    # This test might be wrong - the DB-API spec doesn't require a
    # `.closed` attribute on connections or cursors.
    assert real_db.closed
    assert real_cursor.closed
    assert db.driver_connection() is None


def test_db_closed_errors(db):
    """ interactions with a closed db connection raises a db error. """
    cursor = db._cursor
    db.close()

    with pytest.raises(Cerebrum.database.Error):
        cursor.query(""" select 1 as 'foo' """)

    # TODO: Fixme - this raises a TypeError - as we try to operate on a None
    # object.  This should be a Cerebrum.database.Error
    # with pytest.raises(Cerebrum.database.Error):
    #     db.query(""" select 1 as 'foo' """)


def test_db_close_rollback(db, db_cls):
    """ check that close() causes an implicit rollback. """
    create_sql = "create table foo (x int not null)"
    select_sql = "select * from foo"

    db.execute(create_sql)
    db.close()

    with pytest.raises(Cerebrum.database.Error):
        db2 = db_cls()
        db2.query(select_sql)


#
# commit/rollback + ping tests
#
# This is a bit hairy, as we don't really want our tests to commit anything...
#


def test_commit(db_cls):
    """ Database.commit() transaction commit functionality. """

    # We use two instantiations of Database, each one should have their own
    # transaction, and one should not be able to see the effects of the other,
    # before commit() is performed.
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


def test_rollback(db, table_foo_x):
    """ Database.rollback() transaction rollback functionality. """

    select_sql = 'select * from ' + table_foo_x.name

    for value in (0, 1, 2, 3):
        table_foo_x.insert(db, x=value)

    res = db.query(select_sql)
    assert len(res) == 4

    db.rollback()

    with pytest.raises(Cerebrum.database.DatabaseError) as exc_info:
        db.query(select_sql)

    assert exc_info.value.operation == repr(select_sql)


#
# execute + executemany tests
#


def test_db_executemany(db, table_foo_x):
    rows = 5
    stmt = "insert into {} (x) VALUES (:value)".format(table_foo_x.name)
    param_sets = [{'value': i} for i in range(rows)]

    db.executemany(stmt, param_sets)
    results = list(db.query("select * from " + table_foo_x.name))
    assert len(results) == rows


#
# query + fetch* tests
#


def test_db_query(db, table_foo_x):
    for value in range(5):
        table_foo_x.insert(db, x=value)

    row_sequence = db.query(
        """
        select * from {}
        order by x asc
        """.format(table_foo_x.name),
        fetchall=True,
    )
    assert len(row_sequence) == 5
    assert dict(row_sequence[0]) == {'x': 0}
    assert dict(row_sequence[1]) == {'x': 1}


def test_db_query_iter(db, table_foo_x):
    for value in range(5):
        table_foo_x.insert(db, x=value)

    iter_rows = db.query(
        """
        select * from {}
        order by x asc
        """.format(table_foo_x.name),
        fetchall=False,
    )

    assert dict(next(iter_rows)) == {'x': 0}
    assert dict(next(iter_rows)) == {'x': 1}


def test_db_iter_cursor(db, table_foo_x):
    for value in range(5):
        table_foo_x.insert(db, x=value)

    cursor = db.cursor()
    cursor.execute("select * from {} order by x desc".format(table_foo_x.name))
    rows = list(iter(cursor))
    assert len(rows) == 5
    assert dict(rows[0]) == {'x': 4}


def test_db_rowcount(db, table_foo_x):
    """ Database.execute() database basics. """
    for value in range(5):
        table_foo_x.insert(db, x=value)

    db.query("select * from " + table_foo_x.name)
    assert db.rowcount == 5


def test_db_arraysize_default(db):
    """ Database.execute() database basics. """
    assert db.arraysize == 1


def test_db_fetchone(db, table_foo_x):
    for value in range(5):
        table_foo_x.insert(db, x=value)

    db.execute("select * from " + table_foo_x.name)
    batch = db.fetchone()
    assert len(list(batch)) == 1


def test_db_fetchall(db, table_foo_x):
    rows = 5
    for value in range(rows):
        table_foo_x.insert(db, x=value)

    db.execute("select * from " + table_foo_x.name)
    batch = db.fetchall()
    assert len(list(batch)) == rows


def test_db_fetchmany_default(db, table_foo_x):
    for value in range(5):
        table_foo_x.insert(db, x=value)

    db.execute("select * from " + table_foo_x.name)
    batch = db.fetchmany()
    assert len(list(batch)) == db.arraysize


@pytest.mark.parametrize("arraysize", [1, 3])
def test_db_fetchmany_arraysize(db, table_foo_x, arraysize):
    """ Database.execute() database basics. """
    for value in range(5):
        table_foo_x.insert(db, x=value)

    if arraysize != 1:
        db.arraysize = arraysize
    db.execute("select * from " + table_foo_x.name)
    batch = db.fetchmany()
    assert len(list(batch)) == arraysize


def test_db_fetchmany_override(db, table_foo_x):
    """ Database.execute() database basics. """
    for value in range(5):
        table_foo_x.insert(db, x=value)

    assert db.arraysize == 1
    db.execute("select * from " + table_foo_x.name)
    batch = db.fetchmany(2)
    assert len(list(batch)) == 2


def test_db_description(db, table_foo_xy):
    db.execute("select * from " + table_foo_xy.name)
    desc = db.description
    assert len(desc) == 2


#
# query_1 tests
#


def test_db_query_1_hit(db, table_foo_xy):
    """ query_1 should return a single row object. """
    for value in range(2):
        table_foo_xy.insert(db, x=value)
    hit = db.query_1("select * from {} where x = 1".format(table_foo_xy.name))
    assert dict(hit) == {'x': 1, 'y': None}


def test_db_query_1_hit_unpack(db, table_foo_xy):
    """ query_1 should 'unpack' row if row contains a single column. """
    for value in range(2):
        table_foo_xy.insert(db, x=value)
    hit = db.query_1("select x from {} where x = 1".format(table_foo_xy.name))
    assert hit == 1


def test_db_query_1_too_few(db, table_foo_xy):
    """ query_1 should raise error if no rows are returned. """
    with pytest.raises(Errors.NotFoundError) as exc_info:
        db.query_1("select * from " + table_foo_xy.name)

    error_msg = six.text_type(exc_info.value)
    assert error_msg


def test_db_query_1_too_many(db, table_foo_xy):
    """ query_1 should raise error if multiple rows are returned. """
    for value in range(2):
        table_foo_xy.insert(db, x=value)
    with pytest.raises(Errors.TooManyRowsError) as exc_info:
        db.query_1("select * from " + table_foo_xy.name)

    error_msg = six.text_type(exc_info.value)
    assert error_msg


#
# sequence tests
#


def test_seq_nextval(db, sequence):
    name, start = sequence
    assert db.nextval(name) == start
    assert db.nextval(name) == start + 1


def test_seq_currval(db, sequence):
    name, start = sequence
    db.nextval(name)
    assert db.currval(name) == start
    db.nextval(name)
    assert db.currval(name) == start + 1


def test_seq_setval(db, sequence):
    name, _ = sequence
    value = 4
    assert db.setval(name, value) == value
    assert db.currval(name) == value
    assert db.nextval(name) == value + 1


#
# error type tests
#


@pytest.mark.parametrize(
    'catch, throw',
    [
        ('Database.Error', 'db.IntegrityError'),
        ('Database.Warning', 'db.Warning'),
        ('db.Error', 'db.IntegrityError'),
    ]
)
def test_db_exception_types(db, catch, throw):
    """ Database.Error, correct class types. """

    db = Factory.get('Database')()

    def get_cls(value):
        if value.startswith('db.'):
            return getattr(db, value[3:])
        elif value.startswith('Database.'):
            return getattr(Cerebrum.database, value[9:])
        raise AttributeError('invalid error class: ' + repr(value))

    throw_cls = get_cls(throw)
    catch_cls = get_cls(catch)

    with pytest.raises(catch_cls):
        raise throw_cls()


def test_exception_catch_base(db):
    """ Catch exception raised by the db-driver with Database.Error. """
    with pytest.raises(Cerebrum.database.Error):
        db.execute('create table foo')


def test_exception_catch_instance(db):
    """ Catch exception raised by the db-driver with db.Error. """
    with pytest.raises(db.Error):
        db.execute('create table foo')


def test_multiple_queries_error(db, table_foo_xy):
    """ Database.execute(), multiple queries are forbidden. """

    foo_select = 'select * from ' + table_foo_xy.name

    with pytest.raises(Cerebrum.database.ProgrammingError):
        db.execute(';'.join((foo_select, foo_select)))


def test_missing_table_error(db):
    """ Database.ProgrammingError for non-existing relation. """

    with pytest.raises(Cerebrum.database.ProgrammingError):
        db.execute('select * from efotdzzb')


#
# test column types
#


def test_db_numeric_interaction(db, table_foo_xy):
    """ Database.execute() numeric processing by the backend. """

    values = (0, 1, -10, 10, 2**30, -2**30)

    for value in values:
        table_foo_xy.insert(db, x=value)

    select_sql = 'select * from foo where x = :val'
    for value in values:
        row = db.query_1(select_sql, {'val': value})
        # assert type(row['x']) is type(value) # int -> long, for any numerical
        assert row['x'] == value


def test_unions_with_numeric(db, table_foo_xy, table_baz_zy):
    """ Database.execute(), SQL UNION on numericals returns integer. """

    table_foo_xy.insert(db, x=1, y=2)
    table_baz_zy.insert(db, z=3, y='bar')

    select_sql = 'select x as n from foo union select z as n from baz'
    resultset = db.query(select_sql)

    assert len(resultset) == 2
    for row in resultset:
        assert isinstance(row['n'], six.integer_types)


def test_unicode(db, table_text):

    def select():
        return [r['value']
                for r in db.query('select value from ' + table_text.name)]

    tests = [
        'blåbærsyltetøy',
        'ÆØÅ',
        'ʎøʇǝʇʅsʎsɹæqɐ̥ʅq',
        None,
        'Æ̎̉Ø͂̄Å͐̈'
    ]

    for value in tests:
        table_text.insert(db, value=value)

    results = select()

    print('tests', tests)
    print('results', results)

    assert tests == results


def test_assert_latin1_unicode(db, table_text):
    insert = 'insert into text(value) values (:x)'
    base = 'blåbærsyltetøy'
    with pytest.raises(UnicodeError):
        db.execute(insert, {'x': base.encode('latin1')})


def test_assert_utf8_unicode(db, table_text):
    insert = 'insert into text(value) values (:x)'
    base = 'blåbærsyltetøy'
    with pytest.raises(UnicodeError):
        db.execute(insert, {'x': base.encode('utf-8')})


#
# sql_pattern tests
#
# TODO: The legacy sql_pattern method should be replaced by
# `Cerebrum.database.query_utils.sql_pattern`.  Also, it shouldn't
# be a *method*...
#


def test_sql_pattern_none(db):
    cond, value = db.sql_pattern("t.col", None)
    assert cond == "t.col IS NULL"
    assert value is None


def test_sql_pattern_literal(db):
    cond, value = db.sql_pattern("t.col", "foo bar")
    assert cond == "LOWER(t.col) LIKE :col"
    assert value == "foo bar"


def test_sql_pattern_wildcard(db):
    cond, value = db.sql_pattern("t.col", "fo? bar*")
    assert cond == "LOWER(t.col) LIKE :col"
    assert value == "fo_ bar%"


def test_sql_pattern_literal_case(db):
    cond, value = db.sql_pattern("t.col", "Foo Bar")
    assert cond == "t.col = :col"
    assert value == "Foo Bar"


def test_sql_pattern_wildcard_case(db):
    cond, value = db.sql_pattern("t.col", "Fo? Bar*")
    assert cond == "t.col LIKE :col"
    assert value == "Fo_ Bar%"
