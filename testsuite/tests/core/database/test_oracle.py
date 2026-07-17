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

from Cerebrum.database import oracle


#
# test oracle db class attributes
#


@pytest.mark.parametrize("cls", [oracle.OracleBase, oracle.cx_Oracle])
def test_postgres_macro_table(cls):
    assert cls.macro_table is oracle.ora_macros


@pytest.mark.parametrize("cls", [oracle.OracleBase, oracle.cx_Oracle])
def test_postgres_rdbms_value(cls):
    assert cls.rdbms_id == "Oracle"


#
# test postgres macros
#


def test_pg_macro_table():
    res = oracle.ora_macros("table", {'schema': "cerebrum", 'name': "example"})
    assert res == "cerebrum.example"


def test_pg_macro_now():
    oracle.ora_macros("now", {}) == "SYSDATE"


def test_pg_macro_from_dual():
    oracle.ora_macros("from_dual", {}) == "FROM_DUAL"


def test_pg_macro_sequence_curr():
    res = oracle.ora_macros(
        "sequence",
        {
            'schema': "cerebrum",
            'name': "test_sequence",
            'op': "curr",
        },
    )
    assert res == "cerebrum.test_sequence.currval"


def test_pg_macro_sequence_next():
    res = oracle.ora_macros(
        "sequence",
        {
            'schema': "cerebrum",
            'name': "test_sequence",
            'op': "next",
        },
    )
    assert res == "cerebrum.test_sequence.nextval"


def test_pg_macro_sequence_set():
    with pytest.raises(ValueError, match="Invalid sequence operation"):
        oracle.ora_macros(
            "sequence",
            {
                'schema': "cerebrum",
                'name': "test_sequence",
                'op': "set",
            },
        )
