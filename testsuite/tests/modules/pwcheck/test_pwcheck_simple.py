# -*- coding: utf-8 -*-
"""
Tests for :mod:`Cerebrum.modules.pwcheck.simple`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import functools
import io
import os
import shutil
import tempfile
import textwrap

import gettext
import pytest

from Cerebrum.modules.pwcheck import checker
from Cerebrum.modules.pwcheck import simple


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
# CheckSpaceOrNull tests
#


@pytest.fixture
def check_space():
    return simple.CheckSpaceOrNull()


def test_check_space_valid(check_space):
    checker = check_space
    password = "no-space-or-null"
    result = checker.check_password(password)
    assert not result


@pytest.mark.parametrize(
    "password, errors",
    [
        ("with space", 1),
        ("with-\0-char", 1),
        ("with space and \0 char", 2),
    ],
)
def test_check_space_invalid(check_space, password, errors):
    checker = check_space
    result = checker.check_password(password)
    assert result
    assert len(result) == errors


#
# CheckEightBitChars tests
#


@pytest.fixture
def check_8bit():
    return simple.CheckEightBitChars()


def test_check_8bit_valid(check_8bit):
    checker = check_8bit
    password = "only ascii chars"
    result = checker.check_password(password)
    assert not result


@pytest.mark.parametrize(
    "password",
    [
        "with unicode char=\N{CURRENCY SIGN}",
        "with unicode char=Ø",
    ],
)
def test_check_8bit_invalid(check_8bit, password):
    checker = check_8bit
    result = checker.check_password(password)
    assert result
    assert len(result) == 1


#
# CheckASCIICharacters tests
#


@pytest.fixture
def check_ascii():
    return simple.CheckASCIICharacters()


def test_check_ascii_valid(check_ascii):
    checker = check_ascii
    password = "only ascii chars"
    result = checker.check_password(password)
    assert not result


@pytest.mark.parametrize(
    "password",
    [
        "illegal unicode char=\N{CURRENCY SIGN}",
        "illegal unicode char=Ø",
    ],
)
def test_check_ascii_invalid(check_ascii, password):
    checker = check_ascii
    result = checker.check_password(password)
    assert result
    assert len(result) == 1


#
# CheckLatinCharacters tests
#


@pytest.fixture
def check_latin1():
    return simple.CheckLatinCharacters()


def test_check_latin1_valid(check_latin1):
    checker = check_latin1
    password = "Blåbær \N{CURRENCY SIGN} Øl"
    result = checker.check_password(password)
    assert not result


@pytest.mark.parametrize(
    "password",
    [
        "illegal unicode char=\N{OHM SIGN}",
    ],
)
def test_check_latin1_invalid(check_latin1, password):
    checker = check_latin1
    result = checker.check_password(password)
    assert result
    assert len(result) == 1


#
# CheckIllegalCharacters tests
#

ILLEGAL_CHARS = ("X", "\N{CURRENCY SIGN}", "æ")


@pytest.fixture
def check_chars():
    return simple.CheckIllegalCharacters(ILLEGAL_CHARS)


def test_check_chars_valid(check_chars):
    checker = check_chars
    password = "xylophone, upper case ÆØÅ, and \N{OHM SIGN}"
    result = checker.check_password(password)
    assert not result


def test_check_chars_invalid(check_chars):
    checker = check_chars
    password = "Xylophone and \N{CURRENCY SIGN}"
    result = checker.check_password(password)
    assert result
    assert len(result) == 2


#
# CheckSimpleCharacterGroups tests
#


def _check_groups(ngroups, nchars, password):
    checker = simple.CheckSimpleCharacterGroups(min_groups=ngroups,
                                                min_chars_per_group=nchars)
    return checker.check_password(password)


@pytest.mark.parametrize(
    "ngroups, nchars, password",
    [
        (1, 1, "x"),            # one char in one group
        (2, 2, "FooBar"),       # two uppercase, four lowercase
        (4, 1, "1xA?"),         # four groups
        (2, 4, "1234abcd?"),    # two groups of four
    ],
)
def test_check_groups_valid(ngroups, nchars, password):
    assert not _check_groups(ngroups, nchars, password)


@pytest.mark.parametrize(
    "ngroups, nchars, password",
    [
        (1, 1, ""),
        (2, 2, "Foobar"),
        (4, 1, "123xyz?!"),
        (2, 4, "123abcd?"),
    ],
)
def test_check_groups_invalid(ngroups, nchars, password):
    assert _check_groups(ngroups, nchars, password)


#
# CheckSimpleEntropyCalculator tests
#


@pytest.fixture
def check_entropy():
    return simple.CheckSimpleEntropyCalculator(
        min_chars_per_group=2,
        min_groups=3,
        min_required_entropy=30,
    )


def test_check_entropy_requirement(check_entropy):
    assert check_entropy.requirement


@pytest.mark.parametrize(
    "password, entropy",
    [
        # test length scores
        ("1", 4),
        ("123", 8),
        ("123456789", 19),  # actually 19.5, but we round down
        ("123456789012345678901", 37),
        # test character bonuses
        ("Foo bar baz", 28),  # three groups, but only two with >= 2 chars
        ("Foo Bar Baz", 30),  # three groups with >= 2 chars
    ],
)
def test_entropy(check_entropy, password, entropy):
    assert check_entropy.get_entropy(password) == entropy


@pytest.mark.parametrize(
    "password",
    [
        "123456789012345678901",    # entropy = 37
        "Foo Bar Baz",              # entropy = 30
    ],
)
def test_check_entropy_valid(check_entropy, password):
    assert not check_entropy.check_password(password)


@pytest.mark.parametrize(
    "password",
    [
        "123456789",    # entropy = 19
        "Foo bar baz",  # entropy = 28
    ],
)
def test_check_entropy_invalid(check_entropy, password):
    assert check_entropy.check_password(password)


#
# CheckLengthMixin tests
#


def _check_length(minlen, maxlen, password):
    checker = simple.CheckLengthMixin(min_length=minlen, max_length=maxlen)
    return checker.check_password(password)


@pytest.mark.parametrize(
    "minlen, maxlen, password",
    [
        (0, 0, ""),
        (8, 8, "12345678"),
        (8, None, "12345678 this is a long password"),
        (None, 12, "123456789012"),
    ],
)
def test_check_length_valid(minlen, maxlen, password):
    assert not _check_length(minlen, maxlen, password)


@pytest.mark.parametrize(
    "minlen, maxlen, password",
    [
        (0, 0, "x"),
        (3, None, "x"),
        (None, 3, "1234"),
    ],
)
def test_check_length_invalid(minlen, maxlen, password):
    assert _check_length(minlen, maxlen, password)


#
# CheckMultipleCharacterSets tests
#


@pytest.fixture
def check_legacy_groups():
    return simple.CheckMultipleCharacterSets()


@pytest.mark.parametrize(
    "password",
    [
        "abcX3def",
        "ABCdef12",
        "abc123?!",
    ],
)
def test_check_legacy_groups_valid(check_legacy_groups, password):
    assert not check_legacy_groups.check_password(password)


@pytest.mark.parametrize(
    "password",
    [
        "ABCdefg1",             # only number/special in last position
        "Abc123de",             # only upper case in first position
        "12345678abcX3def",     # no variation in first 8 chars
    ],
)
def test_check_legacy_groups_invalid(check_legacy_groups, password):
    assert check_legacy_groups.check_password(password)


#
# CheckCharacterSequence tests
#


@pytest.fixture
def check_sequence():
    return simple.CheckCharacterSequence(char_seq_length=3)


@pytest.mark.parametrize(
    "password",
    [
        "abxcd",  # almost alphabetical
        "qwop",   # almost keybaord row
        "1245",   # almost numerical
    ],
)
def test_check_sequence_valid(check_sequence, password):
    assert not check_sequence.check_password(password)


@pytest.mark.parametrize(
    "password",
    [
        "qwerty",           # keyboard row
        "ASdf",             # keyboard row
        "abcdef",           # alphabet
        "12345678",         # numbers
    ],
)
def test_check_sequence_invalid(check_sequence, password):
    assert check_sequence.check_password(password)


#
# CheckRepeatedPattern tests
#


@pytest.fixture
def check_repeat():
    return simple.CheckRepeatedPattern()


@pytest.mark.parametrize(
    "password",
    [
        "ababa",            # short patterns must be repeated thrice
        "abcddcab",         # almost reversed pattern
        "12345678abccba",   # sequence OK after 8 chars
    ],
)
def test_check_repeat_valid(check_repeat, password):
    assert not check_repeat.check_password(password)


@pytest.mark.parametrize(
    "password",
    [
        "ababab",
        "abcdabcd",
        "abcddcba",
    ],
)
def test_check_repeat_invalid(check_repeat, password):
    assert check_repeat.check_password(password)


#
# CheckUsernameExact tests
#


@pytest.fixture
def check_uname():
    return simple.CheckUsernameExact()


username = "foo"
example_user = type(str("Account"), (object,), {"account_name": "foo"})
non_user = type(str("Group"), (object,), {})


@pytest.mark.parametrize(
    "account, password",
    [
        (None, "foo bar"),
        (non_user, "foo bar"),
        (example_user, "bar oof baz"),
    ],
)
def test_check_uname_valid(check_uname, account, password):
    assert not check_uname.check_password(password, account=account)


@pytest.mark.parametrize(
    "account, password",
    [
        (example_user, "foo bar"),
        (example_user, "bar foo baz"),
    ],
)
def test_check_uname_invalid(check_uname, account, password):
    assert check_uname.check_password(password, account=account)


#
# CheckUsername tests
#


@pytest.fixture
def check_uname_rev():
    return simple.CheckUsername()


username = "foo"
example_user = type(str("Account"), (object,), {"account_name": "foo"})
non_user = type(str("Group"), (object,), {})


@pytest.mark.parametrize(
    "account, password",
    [
        (None, "foo bar"),
        (non_user, "foo bar"),
        (example_user, "bar baz"),
    ],
)
def test_check_uname_rev_valid(check_uname_rev, account, password):
    assert not check_uname_rev.check_password(password, account=account)


@pytest.mark.parametrize(
    "account, password",
    [
        (example_user, "foo bar"),
        (example_user, "bar oof baz"),
    ],
)
def test_check_uname_rev_invalid(check_uname_rev, account, password):
    assert check_uname_rev.check_password(password, account=account)


# TODO: Person name checks

#
# CheckLettersSpacesOnly tests
#


@pytest.fixture
def check_words():
    return simple.CheckLettersSpacesOnly(extra_chars=":?!")


def test_check_words_valid(check_words):
    checker = check_words
    password = "only word chars?!"
    assert not checker.check_password(password)


@pytest.mark.parametrize(
    "password",
    [
        "illegal char: 7",
        "illegal char: #",
    ],
)
def test_check_words_invalid(check_words, password):
    checker = check_words
    assert checker.check_password(password)


#
# CheckNumberOfDigits tests
#


@pytest.fixture
def check_digits():
    return simple.CheckNumberOfDigits(digits=2)


def test_check_digits_valid(check_digits):
    checker = check_digits
    password = "digits12"
    assert not checker.check_password(password)


@pytest.mark.parametrize(
    "password",
    [
        "only 1 digit",
        "no digits",
    ],
)
def test_check_digits_invalid(check_digits, password):
    checker = check_digits
    assert checker.check_password(password)


#
# CheckNumberOfLetters tests
#


@pytest.fixture
def check_letters():
    return simple.CheckNumberOfLetters(letters=3)


def test_check_letters_valid(check_letters):
    checker = check_letters
    password = "123abc"
    assert not checker.check_password(password)


@pytest.mark.parametrize(
    "password",
    [
        "123xy?!",
        "12345678",
    ],
)
def test_check_letters_invalid(check_letters, password):
    checker = check_letters
    assert checker.check_password(password)


#
# CheckMixedCasing tests
#


@pytest.fixture
def check_mixed_case():
    return simple.CheckMixedCasing()


def test_check_mixed_case_valid(check_mixed_case):
    checker = check_mixed_case
    password = "ABCdef"
    assert not checker.check_password(password)


@pytest.mark.parametrize(
    "password",
    [
        "abcdef",
        "123ABC",
    ],
)
def test_check_mixed_case_invalid(check_mixed_case, password):
    checker = check_mixed_case
    assert checker.check_password(password)
