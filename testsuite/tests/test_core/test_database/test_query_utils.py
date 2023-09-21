# -*- coding: utf-8 -*-
"""
Tests for Cerebrum.database.query_utils
"""
import datetime

import pytest

import Cerebrum.database.query_utils

Range = Cerebrum.database.query_utils._Range


def test_range_init():
    r = Range(gt='bar', le='foo')
    assert r.start == 'bar'
    assert not r.start_inclusive
    assert r.stop == 'foo'
    assert r.stop_inclusive


def test_range_invalid_init_args():
    with pytest.raises(TypeError):
        # gt and ge is incompatible
        Range(gt=3, ge=4)

    with pytest.raises(TypeError):
        # lt and le is incompatible
        Range(lt=4, le=3)

    with pytest.raises(TypeError):
        # no range given - nothing to do
        Range()

    with pytest.raises(ValueError):
        # a value cannot be greater than 2 *and* less than 1
        Range(gt=2, lt=1)


def test_range_repr():
    rr = repr(Range(gt='bar', le='foo'))
    assert rr == "<_Range gt='bar' le='foo'>"


def test_range_select_gt():
    r = Range(gt=3)
    conds, binds = r.get_sql_select('testcol', 'testval')
    assert conds == '(testcol > :testval_start)'
    assert binds == {'testval_start': 3}


def test_range_select_ge():
    r = Range(ge=3)
    conds, binds = r.get_sql_select('testcol', 'testval')
    assert conds == '(testcol >= :testval_start)'
    assert binds == {'testval_start': 3}


def test_range_select_lt():
    r = Range(lt=3)
    conds, binds = r.get_sql_select('testcol', 'testval')
    assert conds == '(testcol < :testval_stop)'
    assert binds == {'testval_stop': 3}


def test_range_select_le():
    r = Range(le=3)
    conds, binds = r.get_sql_select('testcol', 'testval')
    assert conds == '(testcol <= :testval_stop)'
    assert binds == {'testval_stop': 3}


def test_range_select_gt_le():
    r = Range(gt=0, le=3)
    conds, binds = r.get_sql_select('testcol', 'testval')
    assert conds == '(testcol > :testval_start AND testcol <= :testval_stop)'
    assert binds == {'testval_start': 0, 'testval_stop': 3}


def test_range_select_ge_lt():
    r = Range(ge=0, lt=3)
    conds, binds = r.get_sql_select('testcol', 'testval')
    assert conds == '(testcol >= :testval_start AND testcol < :testval_stop)'
    assert binds == {'testval_start': 0, 'testval_stop': 3}


Pattern = Cerebrum.database.query_utils.Pattern
TS = Pattern.TOKEN_STRING
TW = Pattern.TOKEN_WILDCARD


def test_tokenize_wildcard():
    tokens = list(Pattern.tokenize('foo-*-bar'))
    assert tokens == [(TS, 'foo-'), (TW, '*'), (TS, '-bar')]


def test_tokenize_wildcard_sequence():
    tokens = list(Pattern.tokenize('foo-?*-bar'))
    assert tokens == [(TS, 'foo-'), (TW, '?'), (TW, '*'), (TS, '-bar')]


def test_tokenize_start_and_end_on_wildcard():
    tokens = list(Pattern.tokenize('*foo-bar*'))
    assert tokens == [(TW, '*'), (TS, 'foo-bar'), (TW, '*')]


def test_tokenize_escape():
    # escape a wildcard symbol
    tokens = list(Pattern.tokenize(r'foo-\*-bar'))
    assert tokens == [(TS, 'foo-*-bar')]


def test_tokenize_literal_escape():
    # escape the escape character
    tokens = list(Pattern.tokenize(r'foo-\\*-bar'))
    assert tokens == [(TS, 'foo-\\'), (TW, '*'), (TS, '-bar')]


def test_tokenize_invalid_escape():
    # cannot end on an excape character without anything to escape
    # this is pretty much the only actual syntax error
    with pytest.raises(ValueError):
        list(Pattern.tokenize('foo\\'))


def test_tokenize_escape_anything():
    # can escape any character, even if it has no special meaning
    tokens = list(Pattern.tokenize(r'f\oo-\bar\-baz'))
    assert tokens == [(TS, 'foo-bar-baz')]


def test_pattern_init():
    p = Pattern('foo-*-bar')
    assert p.pattern == 'foo-*-bar'
    assert p.tokens == ((TS, 'foo-'), (TW, '*'), (TS, '-bar'))
    assert p.case_sensitive


def test_pattern_init_case_insensitive():
    p = Pattern('foo-*-bar', case_sensitive=False)
    assert not p.case_sensitive


def test_pattern_repr():
    rr = repr(Pattern('foo-*-bar'))
    assert rr == "<Pattern pattern='foo-*-bar' case_sensitive=True>"


def test_pattern_dwim():
    pa = Pattern.dwim('Foo-*-Bar')
    assert pa.pattern == 'Foo-*-Bar'
    assert pa.case_sensitive

    pa = Pattern.dwim('foo-*-bar')
    assert pa.pattern == 'foo-*-bar'
    assert not pa.case_sensitive


def test_pattern_sql():
    p = Pattern('Foo-*-Bar')
    assert p.sql_pattern == 'Foo-%-Bar'


def test_pattern_sql_escape():
    p = Pattern('% * _ ?')
    assert p.sql_pattern == r'\% % \_ _'


def test_sql_select_case_sensitive():
    r = Pattern('Foo-*-Bar')
    cond, binds = r.get_sql_select('testcol', 'testval')
    assert cond == "(testcol LIKE :testval)"
    assert binds == {'testval': 'Foo-%-Bar'}


def test_sql_select_case_insensitive():
    r = Pattern('Foo-*-Bar', case_sensitive=False)
    cond, binds = r.get_sql_select('testcol', 'testval')
    assert cond == "(testcol ILIKE :testval)"
    assert binds == {'testval': 'Foo-%-Bar'}


pattern_helper = Cerebrum.database.query_utils.pattern_helper


def test_pattern_helper_blank():
    # check that no args gives no conds
    conds, binds = pattern_helper("foo")
    assert conds is None
    assert not binds


def test_pattern_helper_nullable():
    # check that the nullable argument works as expeceted
    cond, binds = pattern_helper("foo", value=None, nullable=False)
    assert cond is None
    assert not binds

    cond, binds = pattern_helper("foo", value=None, nullable=True)
    assert cond == "foo IS NULL"
    assert not binds


def test_pattern_helper_values_and_patterns():
    # check that normal use works as expected
    cond, binds = pattern_helper("foo", value="Foo", icase_pattern="Foo-*-Baz")
    assert cond == "((foo = :foo) OR (foo ILIKE :foo_i_pattern))"
    assert binds == {
        'foo': "Foo",
        'foo_i_pattern': "Foo-%-Baz",
    }


def test_pattern_helper_null_and_patterns():
    cond, binds = pattern_helper("foo",
                                 value=None,
                                 case_pattern="Foo-*-Bar",
                                 nullable=True)
    assert cond == ("(foo IS NULL OR (foo LIKE :foo_c_pattern))")
    assert binds == {"foo_c_pattern": "Foo-%-Bar"}


date_helper = Cerebrum.database.query_utils.date_helper


def test_date_helper_blank():
    # check that no args gives no conds
    conds, binds = date_helper("foo")
    assert conds is None
    assert not binds


def test_date_helper_nullable():
    # check that the nullable argument works as expeceted
    cond, binds = date_helper("foo", value=None, nullable=False)
    assert cond is None
    assert not binds

    cond, binds = date_helper("foo", value=None, nullable=True)
    assert cond == "foo IS NULL"
    assert not binds


def test_date_helper_range():
    # check that ranges work as normal
    a, b = datetime.date(2012, 1, 3), datetime.date(2012, 1, 6)
    cond, binds = date_helper("foo", gt=a, lt=b)
    assert cond == "(foo > :foo_range_start AND foo < :foo_range_stop)"
    assert binds == {"foo_range_start": a, "foo_range_stop": b}


def test_date_helper_values_and_range():
    a, b, c = [datetime.date(2012, 1, d) for d in (1, 3, 5)]
    cond, binds = date_helper("foo", value=(a, b), ge=c)
    assert cond == ("((foo IN (:foo0, :foo1))"
                    " OR (foo >= :foo_range_start))")
    assert binds == {"foo0": a, "foo1": b, "foo_range_start": c}


def test_date_helper_null_and_range():
    d = datetime.date(2012, 1, 3)
    cond, binds = date_helper("foo", value=None, ge=d, nullable=True)
    assert cond == ("(foo IS NULL OR (foo >= :foo_range_start))")
    assert binds == {"foo_range_start": d}


int_helper = Cerebrum.database.query_utils.int_helper


def test_int_helper_blank():
    # check that no args gives no conds
    conds, binds = int_helper("foo")
    assert conds is None
    assert not binds


def test_int_helper_nullable():
    # check that the nullable argument works as expeceted
    cond, binds = int_helper("foo", value=None, nullable=False)
    assert cond is None
    assert not binds

    cond, binds = int_helper("foo", value=None, nullable=True)
    assert cond == "foo IS NULL"
    assert not binds


def test_int_helper_range():
    # check that ranges work as normal
    cond, binds = int_helper("foo", gt=3, lt=6)
    assert cond == "(foo > :foo_range_start AND foo < :foo_range_stop)"
    assert binds == {"foo_range_start": 3, "foo_range_stop": 6}


def test_int_helper_values_and_range():
    cond, binds = int_helper("foo", value=(1, 3, 5), ge=7)
    assert cond == ("((foo IN (:foo0, :foo1, :foo2))"
                    " OR (foo >= :foo_range_start))")
    assert binds == {"foo0": 1, "foo1": 3, "foo2": 5, "foo_range_start": 7}


def test_int_helper_null_and_range():
    cond, binds = int_helper("foo", value=None, ge=7, nullable=True)
    assert cond == ("(foo IS NULL OR (foo >= :foo_range_start))")
    assert binds == {"foo_range_start": 7}
