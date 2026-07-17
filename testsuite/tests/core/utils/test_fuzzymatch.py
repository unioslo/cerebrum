# encoding: utf-8
"""
Tests for mod:`Cerebrum.utils.fuzzymatch`.
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


rdl_score = Cerebrum.utils.fuzzymatch.rdl_score
rdl_score_examples = [
    ("foo-bar", "foo-bar", 1.0),  # equal should score 1
    ("foo-bar", "", 0.0),  # completely un-equal should score 0
    ("kitten", "sitting", 0.57),  # ~ (1 - 3/7)
    ("guinea", "guyana", 0.50),
    ("french", "france", 0.66),  # ~ (1 - 2/6)
]


@pytest.mark.parametrize("a, b, expected", rdl_score_examples)
def test_rdl_score(a, b, expected):
    assert abs(rdl_score(a, b) - expected) < 0.01


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


lcs_score = Cerebrum.utils.fuzzymatch.lcs_score
lcs_score_examples = [
    ("foo-bar", "foo-bar", 1.0),
    ("foo-bar", "", 0.0),
    ("kitten", "sitting", 0.57),
    ("guinea", "guyana", 0.66),
    ("french", "france", 0.66),
]


@pytest.mark.parametrize("a, b, expected", lcs_score_examples)
def test_lcs_score(a, b, expected):
    assert abs(lcs_score(a, b) - expected) < 0.01


#
# words_diff
#
words_diff = Cerebrum.utils.fuzzymatch.words_diff


def test_words_diff_all_words_present():
    assert words_diff("foo baz", "foo bar baz") == 0


def test_words_diff_all_words_present_reversed():
    assert words_diff("foo bar baz", "foo baz") == 0


def test_words_diff_one_accented_char():
    assert words_diff("foo bar", "foo bxr baz") == 1


def test_words_diff_longer_distance():
    # a and b has words with rdl distances: 0 + 3 + 3 + 2
    a = "foo kitten guinea french"
    b = "foo sitting guyana france"
    assert words_diff(a, b) == 8


def test_words_diff_threshold():
    # a and b has words with rdl distances: 0 + 3 + 3 + 2
    a = "foo kitten guinea french"
    b = "foo sitting guyana france"
    actual_diff = 8
    threshold = 3
    diff = words_diff(a, b, threshold=threshold)

    # The threshold should be broken after after "guinea".  The actual diff
    # should be *actual_diff*, but that isn't important.  We just want to know
    # that:
    #
    # That the diff can be used by the caller to indicate that a threshold was
    # broken
    assert diff > threshold

    # ... and that the threshold actually stops the comparison, which should
    # cut down processing time
    assert diff < actual_diff
