# -*- coding: utf-8 -*-
"""
Tests for :mod:`Cerebrum.database.row_factory`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

from Cerebrum.database import row_factory


#
# Fixture and test data
#


# Some rows to insert into our table fixture
ROW_DICTS = [
    {'int': 1, 'text': "foo"},
    {'int': 2, 'text': "foo"},
    {'int': 3, 'text': "bar"},
    {'int': 4, 'text': "bar"},
]
ROW_TUPLES = [
    (d['int'], d['text'])
    for d in ROW_DICTS
]


@pytest.fixture(autouse=True)
def table(database):
    """ a table with our *ROW_DICTS* rows. """
    database.execute(
        """
        CREATE TABLE [:table schema=cerebrum name=row_test]
        (
            int INT NOT NULL,
            text TEXT NOT NULL
        )
        """
    )
    database.executemany(
        """
        INSERT INTO [:table schema=cerebrum name=row_test]
          (int, text)
        VALUES
          (:int, :text)
        """,
        ROW_DICTS,
    )


@pytest.fixture
def cursor(database, table):
    """ a cursor that selects our *ROW_DICTS* rows. """
    cur = database.cursor()
    cur.execute(
        """
        SELECT int, text FROM [:table schema=cerebrum name=row_test]
        ORDER BY int ASC, text ASC
        """
    )
    return cur


@pytest.fixture
def fields(cursor):
    """ field names from the *cursor* fixture. """
    # PEP-249 DB-API description: (name, type_code, ...)
    return [d[0].lower() for d in cursor.description]


#
# Tests
#


def test_db_row_iterator(cursor):
    iterator = iter(row_factory._DbRowIterator(cursor, tuple))
    for i in range(4):
        assert next(iterator) == ROW_TUPLES[i]
    with pytest.raises(StopIteration):
        next(iterator)


@pytest.fixture
def db_row_iterator(cursor):
    return row_factory._DbRowIterator(cursor, tuple)


def test_db_row_iterator_init(db_row_iterator):
    assert db_row_iterator


def test_db_row_iterator_iter(db_row_iterator):
    assert iter(db_row_iterator) is db_row_iterator


def test_db_row_iterator_next(db_row_iterator):
    for i in range(4):
        assert next(db_row_iterator) == ROW_TUPLES[i]
    with pytest.raises(StopIteration):
        next(db_row_iterator)


@pytest.mark.parametrize("size", [None, 1, 2])
def test_resultiter(cursor, size):
    iterator = row_factory._resultiter(cursor, size=size)
    for i in range(4):
        assert next(iterator) == ROW_TUPLES[i]
    with pytest.raises(StopIteration):
        next(iterator)


def test_iter_rows(cursor, fields):
    iterator = row_factory.iter_rows(cursor, fields)
    for i in range(4):
        assert dict(next(iterator)) == ROW_DICTS[i]
    with pytest.raises(StopIteration):
        next(iterator)


def test_list_rows_size(cursor, fields):
    sequence = row_factory.list_rows(cursor, fields)
    assert len(sequence) == 4


def test_list_rows_items(cursor, fields):
    sequence = row_factory.list_rows(cursor, fields)
    for i in range(4):
        assert dict(sequence[i]) == ROW_DICTS[i]
