# -*- coding: utf-8 -*-
"""
Tests for :mod:`Cerebrum.database.lexer_sqlparse`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest
import six

from Cerebrum.database import lexer_sqlparse
from Cerebrum.database import paramstyles
from Cerebrum.database import macros


@pytest.fixture
def paramstyle():
    return paramstyles.Named()


@pytest.fixture
def lexer(paramstyle):
    return lexer_sqlparse.get_sqlparse_stack(paramstyle, macros.common_macros)


@pytest.fixture
def translate(paramstyle):
    def _translate(stmt):
        return lexer_sqlparse._translate(stmt, paramstyles.Named,
                                         macros.common_macros)
    return _translate


def test_parse_simple(lexer, paramstyle):
    results = list(
        lexer.run("""select * from foo""", None)
    )
    assert len(results) == 1
    assert not paramstyle.names
    result = six.text_type(results[0])
    assert result == "select * from foo"


def test_parse_macro(lexer, paramstyle):
    """ our parser can translate cerebrum macros """
    results = list(
        lexer.run("""select * from [:table schema=cerebrum name=foo]""", None)
    )
    assert len(results) == 1
    assert not paramstyle.names
    result = six.text_type(results[0])
    assert result == "select * from foo"


def test_placeholder(lexer, paramstyle):
    """ our parser detects and registers placeholders. """
    results = list(
        lexer.run("select * from foo where bar=:baz", None)
    )
    assert len(results) == 1
    assert paramstyle.names == ["baz"]
    result = six.text_type(results[0])
    assert result == "select * from foo where bar=:baz"


def test_placeholder_invalid(lexer, paramstyle):
    with pytest.raises(ValueError) as exc_info:
        list(lexer.run("select * from foo where bar=%(baz)s", None))

    error_msg = six.text_type(exc_info.value)
    assert "invalid placeholder style" in error_msg


def test_fix_whitespace(lexer, paramstyle):
    # note the missing whitespace between the '[:table]' macro and 'where'
    results = list(
        lexer.run("select * from "
                  "[:table schema=cerebrum name=foo]where bar='baz'", None)
    )
    assert len(results) == 1
    assert not paramstyle.names
    result = six.text_type(results[0])
    assert result == "select * from foo where bar='baz'"


def test_translate(translate):
    stmt, params = translate(
        "select * from [:table schema=cerebrum name=foo] "
        "where bar=:baz and date=[:now]"
    )
    assert params.names == ["baz"]
    assert stmt == (
        "select * from foo "
        "where bar=:baz and date=CURRENT_TIMESTAMP"
    )


def test_translate_multiple(translate):
    with pytest.raises(ValueError) as exc_info:
        translate("select * from foo; select * from bar;")

    error_msg = six.text_type(exc_info.value)
    assert "after end of SQL statement" in error_msg
