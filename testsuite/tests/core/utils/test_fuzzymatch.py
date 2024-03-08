"""
Tests for Cerebrum.utils.fuzzymatch.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

import Cerebrum.utils.fuzzymatch


#
# restricted_damerau_levenshtein
#
rdl = Cerebrum.utils.fuzzymatch.restricted_damerau_levenshtein


def test_rdl_both_empty():
    """ Empty strings are equal (no distance). """
    assert rdl("", "") == 0


def test_rdl_one_empty():
    """ Distance is length of non-empty when comparing with empty. """
    nonempty = "nonempty"
    distance = len(nonempty)
    assert rdl("", nonempty) == distance


def test_rdl_equal():
    """ Distance is zero for two equal strings. """
    string = "equal"
    assert rdl(string, string) == 0


rdl_examples = [
    ("kitten", "sitting", 3),
    ("guinea", "guyana", 3),
    ("french", "france", 2),
]


@pytest.mark.parametrize("a, b, expected", rdl_examples)
def test_rdl_distance(a, b, expected):
    assert rdl(a, b) == expected


@pytest.mark.parametrize("a, b, expected", rdl_examples)
def test_rdl_reversed(a, b, expected):
    assert rdl(b, a) == expected


#
# longest_common_subsequence
#
lcs = Cerebrum.utils.fuzzymatch.longest_common_subsequence


def test_lcs_both_empty():
    """ Empty strings have nothing in common. """
    assert lcs("", "") == ""


def test_lcs_one_empty():
    """ Empty strings have nothing in common. """
    assert lcs("", "nonempty") == ""


def test_lcs_equal():
    """ Result is the input string if both inputs are the same. """
    string = "equal"
    assert lcs(string, string) == string


lcs_examples = [
    # These examples are upper-cased to easily show the similarities.
    # All strings should be lowercased in tests.
    ("kITTeN", "sITTiNg", "ITTN"),
    ("GUiNeA", "GUyaNA", "GUNA"),
    ("FReNCh", "FRaNCe", "FRNC"),
]


@pytest.mark.parametrize("a, b, expected", lcs_examples)
def test_lcs(a, b, expected):
    assert lcs(a.lower(), b.lower()) == expected.lower()


@pytest.mark.parametrize("a, b, expected", lcs_examples)
def test_lcs_reversed(a, b, expected):
    assert lcs(b.lower(), a.lower()) == expected.lower()


#
# words_diff
#
words_diff = Cerebrum.utils.fuzzymatch.words_diff


def test_words_diff_all_words_present():
    assert words_diff("foo baz", "foo bar baz") == 0


def test_words_diff_one_accented_char():
    assert words_diff("foo bar", "foo bxr baz") == 1
