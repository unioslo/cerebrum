# -*- coding: utf-8 -*-
"""
Tests for :mod:`Cerebrum.database.postgres`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

from Cerebrum.database import postgres


def test_get_pg_savepoint_id():
    spid = postgres.get_pg_savepoint_id()
    assert len(spid) == 42


@pytest.mark.parametrize(
    "name, expected",
    [
        (
            "Cerebrum.testsuite",
            "cerebrum (Cerebrum.testsuite)",
        ),
        (
            "blåbærsyltetøy",
            "cerebrum (blaabaersyltetoy)",
        ),
        (
            "123456789 123456789 123456789 123456789 123456789 1234567890",
            "cerebrum (123456789 123456789 123456789 123456789 123456789...)",
        ),
    ],
    ids=[
        "module",
        "unicode",
        "long",
    ]
)
def test_format_pg_application_name(name, expected):
    result = postgres._format_pg_app_name(name)
    assert len(result) < 64
    assert result == expected


#
# test postgres db class attributes
#


@pytest.mark.parametrize("cls", [postgres.PostgreSQLBase, postgres.PsycoPG2])
def test_postgres_macro_table(cls):
    assert cls.macro_table is postgres.pg_macros


@pytest.mark.parametrize("cls", [postgres.PostgreSQLBase, postgres.PsycoPG2])
def test_postgres_rdbms_value(cls):
    assert cls.rdbms_id == "PostgreSQL"


#
# test postgres macros
#


def test_pg_macro_now():
    postgres.pg_macros("now", {}) == "NOW()"


def test_pg_macro_sequence_curr():
    res = postgres.pg_macros(
        "sequence",
        {
            'schema': "cerebrum",
            'name': "test_sequence",
            'op': "curr",
        },
    )
    assert res == "currval('test_sequence')"


def test_pg_macro_sequence_next():
    res = postgres.pg_macros(
        "sequence",
        {
            'schema': "cerebrum",
            'name': "test_sequence",
            'op': "next",
        },
    )
    assert res == "nextval('test_sequence')"


def test_pg_macro_sequence_set():
    res = postgres.pg_macros(
        "sequence",
        {
            'schema': "cerebrum",
            'name': "test_sequence",
            'op': "set",
            'val': "3",
        },
    )
    assert res == "setval('test_sequence', 3)"


def test_pg_macro_sequence_invalid_op():
    with pytest.raises(ValueError, match="Invalid sequence operation"):
        postgres.pg_macros(
            "sequence",
            {
                'schema': "cerebrum",
                'name': "test_sequence",
                'op': "foo",
            },
        )


def test_pg_macro_sequence_invalid_params():
    with pytest.raises(TypeError):
        postgres.pg_macros(
            "sequence",
            {
                'name': "test_sequence",
            },
        )


def test_pg_macro_sequence_start_deprecated():
    with pytest.deprecated_call():
        res = postgres.pg_macros("sequence_start", {'value': "3"})
        assert res == "START 3"
