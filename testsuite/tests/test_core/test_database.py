# -*- coding: utf-8 -*-
"""
Tests for Cerebrum.database

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
import pytest

import Cerebrum.database
from Cerebrum.Utils import Factory


# TODO: This could be done better...
# TODO: This test module should we rewritten to use pytest

def create_table(db, table_name, *table_defs):
    """
    Create a table.

    :param str table_name: The name of the temporary table
    :param str *: column definitions
    """
    db.execute('create table %s (%s)' % (table_name, ','.join(table_defs)))
    return table_name


@pytest.fixture
def db():
    try:
        database = Factory.get('Database')()
        database.commit = database.rollback
        yield database
    finally:
        database.rollback()


class _Table(object):

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
    t = _Table('foo', x='int not null')
    db.execute(t.create)
    return t


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


def test_db_simple_query(db, table_foo_x):
    """ Database.execute() database basics. """
    select_sql = 'select count(*) as one from ' + table_foo_x.name

    lo, hi = 1, 4
    for value in range(lo, hi):
        table_foo_x.insert(db, x=value)

    count = db.query_1(select_sql)
    assert count == hi - lo


@pytest.fixture
def table_foo_xy(db):
    t = _Table('foo', x='int not null', y='int null')
    db.execute(t.create)
    return t


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


@pytest.fixture
def table_bar_xy(db):
    t = _Table('bar', x='text not null', y='int null')
    db.execute(t.create)
    return t


def test_db_unicode_interaction(db, table_bar_xy):
    """ Database.execute() unicode text. """
    # TODO: What about "øæå"? Should the backend somehow guess the
    # encoding? Or assume some default? Or read it from cereconf?
    values = (u'unicode', u'latin-1:øåæ', unicode('utf-8:øæå', 'utf-8'))

    for value in values:
        table_bar_xy.insert(db, x=value)

    select_sql = 'select * from bar where x = :value'

    for value in values:
        row = db.query_1(select_sql, {"value": value})
        retval = row['x']
        if type(retval) is not unicode:
            retval = unicode(retval, 'utf-8')
        assert retval == value


@pytest.mark.parametrize(
    'catch, throw',
    [
        ('Database.Error', 'db.IntegrityError'),
        ('Database.Warning', 'db.Warning'),
        ('db.Error', 'db.IntegrityError'),
    ])
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


@pytest.fixture
def table_baz_zy(db):
    t = _Table('baz', z='int not null', y='text null')
    db.execute(t.create)
    return t


def test_unions_with_numeric(db, table_foo_xy, table_baz_zy):
    """ Database.execute(), SQL UNION on numericals returns int/long. """

    table_foo_xy.insert(db, x=1, y=2)
    table_baz_zy.insert(db, z=3, y='bar')

    select_sql = 'select x as n from foo union select z as n from baz'
    resultset = db.query(select_sql)

    assert len(resultset) == 2
    for row in resultset:
        assert isinstance(row['n'], (int, long))


def test_all_critical_db_attributes(db):
    """ Database attributes. """

    # - Make sure that Factory.get('Database')() always has a _db, _cursor and
    # the like. Both after the *first* and after the *n'th* call.

    assert hasattr(db, "_db")
    assert hasattr(db, "_cursor")
    # WTF else do we need?


def test_multiple_queries(db, table_foo_xy):
    """ Database.execute(), multiple queries are forbidden. """

    foo_select = 'select * from ' + table_foo_xy.name

    with pytest.raises(Cerebrum.database.ProgrammingError):
        db.execute(';'.join((foo_select, foo_select)))


def test_missing_table(db):
    """ Database.ProgrammingError for non-existing relation. """

    with pytest.raises(Cerebrum.database.ProgrammingError):
        db.execute('select * from efotdzzb')


@pytest.fixture
def table_text(db):
    t = _Table('text', value='text null')
    db.execute(t.create)
    return t


def test_unicode(db, table_text):
    """ Database.rollback() transaction rollback functionality. """

    def select():
        return [r['value']
                for r in db.query('select value from ' + table_text.name)]

    tests = [
        u'blåbærsyltetøy',
        u'ÆØÅ',
        u'ʎøʇǝʇʅsʎsɹæqɐ̥ʅq',
        None,
        u'Æ̎̉Ø͂̄Å͐̈'
    ]

    for value in tests:
        table_text.insert(db, value=value)

    results = select()

    print('tests', tests)
    print('results', results)

    assert tests == results


def test_assert_latin1_unicode(db, table_text):
    """ Database.rollback() transaction rollback functionality. """
    insert = 'insert into text(value) values (:x)'
    base = u'blåbærsyltetøy'

    with pytest.raises(UnicodeError):
        db.execute(insert, {'x': base.encode('latin1')})


def test_assert_utf8_unicode(db, table_text):
    """ Database.rollback() transaction rollback functionality. """

    insert = 'insert into text(value) values (:x)'
    base = u'blåbærsyltetøy'
    with pytest.raises(UnicodeError):
        db.execute(insert, {'x': base.encode('utf-8')})
