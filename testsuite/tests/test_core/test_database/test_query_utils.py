# -*- coding: utf-8 -*-
"""
Tests for Cerebrum.database.query_utils
"""

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
