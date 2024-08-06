# -*- coding: utf-8 -*-
"""
Tests for :mod:`Cerebrum.modules.pwcheck`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest
import six

from Cerebrum.utils import text_compat
from Cerebrum.modules.pwcheck import checker


#
# test password checker with legacy rules
#


@pytest.fixture
def cereconf_legacy(cereconf):
    cereconf.PASSWORD_CHECKS = {
        'rigid': (
            ('length', {'min_length': 10}),
            ('ascii_characters_only', {}),
            ('space_or_null', {}),
            ('simple_character_groups', {'min_groups': 3}),
            ('repeated_pattern', {}),
            ('character_sequence', {'char_seq_length': 3}),
        ),
    }
    return cereconf


@pytest.mark.parametrize(
    "password",
    [
        'mEh19',  # 'length'
        'f0oæL!øåbarmorebarsandfoos',  # 'ascii_characters_only'
        'fO!o\0ba12rmorebarsandfoos',  # 'space_or_null'
        'nIcegOllyPazzWd',  # 'simple_character_groups'
        '2aB!2aB!2aB!2aB!',  # 'character_sequence'
    ],
)
def test_legacy_checks_invalid(cereconf_legacy, password):
    with pytest.raises(checker.RigidPasswordNotGoodEnough):
        checker.check_password(password)


@pytest.mark.parametrize(
    "password",
    [
        "Example-Foo-Bar-Baz",
    ],
)
def test_legacy_checks_valid(cereconf_legacy, password):
    checker.check_password(password)


#
# test password checker with mixed ruleset
#


@pytest.fixture
def cereconf_mixed(cereconf):
    cereconf.PASSWORD_CHECKS = {
        'phrase': (
            ('length', {'min_length': 12}),
        ),
        'rigid': (
            ('ascii_characters_only', {}),
        ),
    }
    return cereconf


@pytest.mark.parametrize(
    "password",
    [
        "1234 67890",  # phrase - too short
        "foo-\N{OHM SIGN}",  # rigid - invalid char
    ],
)
def test_mixed_checks_invalid(cereconf_mixed, password):
    with pytest.raises(checker.PasswordNotGoodEnough):
        checker.check_password(password)


@pytest.mark.parametrize(
    "password",
    [
        "1234 6789 1234",  # phrase - long enough
        "abcd",  # rigid - only ascii
    ],
)
def test_mixed_checks_valid(cereconf_mixed, password):
    checker.check_password(password)


#
# test password checker with passphrase rules
#


@pytest.fixture
def cereconf_phrase(cereconf):
    cereconf.PASSWORD_CHECKS = {
        'phrase': (
            ('length', {'min_length': 12, 'max_length': None}),
            ('num_words', {'min_words': 4, 'min_word_length': 2}),
            ('avg_word_length', {'avg_length': 4})
        ),
    }
    return cereconf


@pytest.mark.parametrize(
    "password",
    [
        'mEh19 alak',  # 'length'
        'rsandfoos Opauiam Minala',  # 'num_words'
        'qwert po vert m',  # 'avg_word_length'
    ],
)
def test_passphrase_checks_invalid(cereconf_phrase, password):
    with pytest.raises(checker.PhrasePasswordNotGoodEnough):
        checker.check_password(password)


@pytest.mark.parametrize(
    "password",
    [
        "this is a valid example password",
    ],
)
def test_passphrase_checks_valid(cereconf_phrase, password):
    checker.check_password(password)


#
# test structured output
#
# This should probably be split into more tests, and should probably also be
# tested with "mixed" style
#


def test_structured_result(cereconf_phrase):
    password = "this is a valid example password"
    result = checker.check_password(password, structured=True)
    assert result['passed']
    assert result['allowed_style'] == "phrase"
    assert result['style'] == "phrase"
    assert len(result['checks']['phrase']) == 3  # three rules

    checks = result['checks']['phrase']
    assert len(checks) == 3  # three rules
    # remap insane data structure
    results = [{'name': n, 'passed': d['passed'], 'errors': d['errors']}
               for check in checks
               for n, d in check.items()]
    assert len([c for c in results if c['passed']]) == 3
    assert len([c for c in results if c['errors']]) == 0


def test_structured_result_with_errors(cereconf_phrase):
    password = "rsandfoos Opauiam Minala"  # 'num_words'
    result = checker.check_password(password, structured=True)
    assert not result['passed']
    assert result['allowed_style'] == "phrase"
    assert result['style'] == "phrase"

    checks = result['checks']['phrase']
    assert len(checks) == 3  # three rules
    results = [{'name': n, 'passed': d['passed'], 'errors': d['errors']}
               for check in checks
               for n, d in check.items()]
    assert len([c for c in results if c['passed']]) == 2
    assert len([c for c in results if c['errors']]) == 1


#
# Test inventory content
#

def test_get_checkers():
    assert checker.get_checkers()


@pytest.mark.parametrize(
    "rule",
    [
        "8bit_characters",
        "ascii_characters_only",
        "avg_word_length",
        "brute_history",
        "character_sequence",
        "current",
        "dictionary",
        "exact_owner_name",
        "exact_username",
        "history",
        "illegal_characters",
        "latin1_characters_only",
        "length",
        "letters_and_spaces_only",
        "mixed_casing",
        "multiple_character_sets",
        "num_words",
        "number_of_digits",
        "number_of_letters",
        "owner_name",
        "repeated_pattern",
        "simple_character_groups",
        "simple_entropy_calculator",
        "space_or_null",
        "username",
    ],
)
def test_checker_loaded(rule):
    """ check that the given rule exists and will be loaded. """
    rules = checker.get_checkers()
    assert rule in rules
    cls = rules[rule]
    assert issubclass(cls, checker.PasswordChecker)

#
# PasswordNotGoodEnough bytes/unicode tests
#


def test_exception_init_text():
    text = "blåbærøl"
    assert checker.PasswordNotGoodEnough(text)


def test_exception_init_bytes():
    text = "blåbærøl".encode("utf-8")
    assert checker.PasswordNotGoodEnough(text)


def test_exception_to_str():
    text = "blåbærøl"
    assert str(checker.PasswordNotGoodEnough(text)) == text_compat.to_str(text)


def test_exception_to_text():
    text = "blåbærøl"
    assert six.text_type(checker.PasswordNotGoodEnough(text)) == text
