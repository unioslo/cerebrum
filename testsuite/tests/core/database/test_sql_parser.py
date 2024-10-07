# -*- coding: utf-8 -*-
"""
Tests for :mod:`Cerebrum.database.sql_parser`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import textwrap

import pytest

from Cerebrum.database import sql_parser
from Cerebrum.testutils import file_utils


@pytest.fixture(scope='module')
def write_dir():
    with file_utils.tempdir_ctx(prefix="test-parse-sql-") as path:
        yield path


class MockVersion(object):

    def __init__(self, major, minor, patch=0, prerelease=None):
        self.version = (major, minor, patch)
        self.prerelease = prerelease


#
# test parse_meta_statement
#


VALID_STATEMENTS = [
    ("category:metainfo", ("category", "metainfo", None)),
    ("category:main/Oracle", ("category", "main", "Oracle")),
]


@pytest.mark.parametrize(
    "line, expected",
    VALID_STATEMENTS,
    ids=[i[0] for i in VALID_STATEMENTS],
)
def test_parse_meta_statement(line, expected):
    assert sql_parser.parse_meta_statement(line) == expected


def test_parse_meta_statement_invalid_tag():
    with pytest.raises(ValueError, match="invalid tag"):
        sql_parser.parse_meta_statement("example:metainfo")


def test_parse_meta_statement_invalid_phase():
    with pytest.raises(ValueError, match="invalid phase"):
        sql_parser.parse_meta_statement("category:create")


def test_parse_meta_statement_empty_phase():
    with pytest.raises(ValueError, match="invalid phase"):
        sql_parser.parse_meta_statement("category:/postgres")


#
# test parse_metainfo
#


def test_parse_metainfo_name():
    assert sql_parser.parse_metainfo("name=foo") == ("name", "foo")


def test_parse_metainfo_version():
    key, value = sql_parser.parse_metainfo("version=1.3")
    assert key == "version"
    assert value == MockVersion(1, 3)


def test_parse_metainfo_invalid_key():
    with pytest.raises(ValueError, match="invalid metainfo key"):
        sql_parser.parse_metainfo("foo=bar")


def test_parse_metainfo_invalid_version():
    with pytest.raises(ValueError, match="invalid version number"):
        sql_parser.parse_metainfo("version=foo")


def test_categorize():
    create = "CREATE TABLE IF NOT EXISTS example_t (value TEXT NOT NULL)"
    drop = "DROP TABLE IF EXISTS example_t"
    sequence = [
        "category:metainfo",
        "name=foo",
        "category:main/postgres",
        create,
        "category:main/oracle",
        create,
        "category:drop",
        drop,
    ]
    items = sql_parser.categorize(sequence)
    assert next(items) == ("category", "metainfo", None, "name=foo")
    assert next(items) == ("category", "main", "postgres", create)
    assert next(items) == ("category", "main", "oracle", create)
    assert next(items) == ("category", "drop", None, drop)


@pytest.fixture
def sql_file(write_dir):
    with file_utils.tempfile_ctx(write_dir, suffix=".sql") as filename:
        yield filename


def test_parse_sql_file(sql_file):
    file_utils.write_text(
        sql_file,
        textwrap.dedent(
            """
            /* Example Cerebrum-SQL file */

            -- example module name
            category:metainfo;
            name=foo;

            category:pre;
            /**
             * the remaining statements doesn't all have their own
             * categories.  This isn't valid in * cerebrum-sql files, but
             * our file parser shouldn't care about that
             */
              CREATE TABLE IF NOT EXISTS example_t (
                  value TEXT NOT NULL
              );
            drop table if exists example_t;

            -- a simple function - functions are typically multiline, and
            -- contains a bunch of semicolons on their own
            CREATE FUNCTION example_func(foo TEXT, bar TEXT)
            RETURNS BOOLEAN AS $$
            DECLARE found BOOLEAN;
            BEGIN
              SELECT (bar = $2) INTO found
              FROM example_t
              WHERE foo = $1;
              RETURN found;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )

    results = list(sql_parser.parse_sql_file(sql_file))
    assert len(results) == 6
    assert results[:3] == [
        "category:metainfo",
        "name=foo",
        "category:pre",
    ]
    assert results[3].startswith("CREATE TABLE")
    assert results[4].startswith("drop table")
    assert results[5].startswith("CREATE FUNCTION")
