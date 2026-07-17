# -*- coding: utf-8 -*-
"""
Tests for :mod:`Cerebrum.modules.pwcheck.phrase`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import gettext
import pytest

from Cerebrum.modules.pwcheck import checker
from Cerebrum.modules.pwcheck import phrase


# Encoding for file contents
ENCODING = "utf-8"


@pytest.fixture(autouse=True)
def _set_language():
    """ set language to 'en' """
    tr = gettext.translation(checker.gettext_domain,
                             localedir=checker.locale_dir,
                             languages=["en"])
    tr.install()


#
# CheckPhraseWords tests
#


def _check_word_count(minwords, minlen, password):
    checker = phrase.CheckPhraseWords(min_words=minwords,
                                      min_word_length=minlen)
    return checker.check_password(password)


@pytest.mark.parametrize(
    "minwords, minlen, password",
    [
        (4, None, "a b c d"),
        (3, 2, "ab cd ef"),
        (3, 3, "foo bar baz"),
        (None, None, ""),
    ],
)
def test_check_word_count_valid(minwords, minlen, password):
    assert not _check_word_count(minwords, minlen, password)


@pytest.mark.parametrize(
    "minwords, minlen, password",
    [
        (4, None, "a b c"),
        (3, 2, "ab d ef"),
        (3, 3, "foo bar"),
    ],
)
def test_check_word_count_invalid(minwords, minlen, password):
    assert _check_word_count(minwords, minlen, password)


#
# CheckPhraseAverageWordLength tests
#


def _check_word_len(avglen, password):
    checker = phrase.CheckPhraseAverageWordLength(avg_length=avglen)
    return checker.check_password(password)


@pytest.mark.parametrize(
    "avglen, password",
    [
        (3, "ab cdef"),
        (7, "example"),
        (3.5, "foo bars"),
        (0, ""),
    ],
)
def test_check_word_len_valid(avglen, password):
    assert not _check_word_len(avglen, password)


@pytest.mark.parametrize(
    "avglen, password",
    [
        (4, "foo bar"),
        (3, ""),
    ],
)
def test_check_word_len_invalid(avglen, password):
    assert _check_word_len(avglen, password)
