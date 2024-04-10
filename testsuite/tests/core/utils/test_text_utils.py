# -*- coding: utf-8 -*-
""" Tests for `Cerebrum.utils.text_utils. """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest
import six

from Cerebrum.utils import text_utils


CHAR_BACKSPACE = six.unichr(0x08)
CHAR_REPLACE = "\N{REPLACEMENT CHARACTER}"


@pytest.mark.parametrize(
    "invalid_type",
    (None, 42, True, [], (), {}, object()),
    ids=(lambda obj: type(obj).__name__),
)
def test_strip_invalid_type(invalid_type):
    """ Providing a non-text as input value is a TypeError. """
    with pytest.raises(TypeError):
        text_utils.strip_category(
            invalid_type,
            text_utils.CATEGORY_CONTROL,
        )


def test_strip_invalid_category():
    """ Providing an unknown category key is a ValueError. """
    with pytest.raises(ValueError) as excinfo:
        text_utils.strip_category("foo", "invalid_category")
    assert "Invalid category" in str(excinfo.value)


def test_replace_prefix():
    # Test providing an actual replacement string to the "protected"
    # _replace_category function
    fmt = "%sfoo%sbar%s"
    text = fmt % (CHAR_BACKSPACE, CHAR_BACKSPACE, CHAR_BACKSPACE)
    expect = fmt % (CHAR_REPLACE, CHAR_REPLACE, CHAR_REPLACE)
    assert text_utils._replace_category(text, text_utils.CATEGORY_CONTROL,
                                        new=CHAR_REPLACE) == expect


@pytest.mark.parametrize(
    "category",
    [text_utils.CATEGORY_CONTROL],
)
def test_strip_empty_string(category):
    """ Empty strings should not be altered. """
    assert text_utils.strip_category("", category) == ""


def test_strip_keep_space():
    """ Space should not be stripped unless it's part of the category. """
    assert text_utils.strip_category(" ", text_utils.CATEGORY_CONTROL) == " "


@pytest.mark.parametrize(
    "n,expected_n",
    ((-1, 0), (0, 3), (1, 2), (2, 1), (3, 0), (4, 0)),
)
def test_strip_maxstrip(n, expected_n):
    """ Only the first *maxstrip* occurrences should be removed. """
    assert len(
        text_utils.strip_category(
            CHAR_BACKSPACE * 3,
            text_utils.CATEGORY_CONTROL,
            maxstrip=n,
        )) == expected_n


def test_strip_exclude():
    """ Excluded characters should not be removed. """
    assert text_utils.strip_category(
        "\t",
        text_utils.CATEGORY_CONTROL,
        exclude="\n",
    ) == ""
    assert text_utils.strip_category(
        "\t\r\n",
        text_utils.CATEGORY_CONTROL,
        exclude="\n",
    ) == "\n"
    assert text_utils.strip_category(
        "\t\r\n",
        text_utils.CATEGORY_CONTROL,
        exclude="\t\n",
    ) == "\t\n"
    assert text_utils.strip_category(
        "\t\t\t\r\n",
        text_utils.CATEGORY_CONTROL,
        exclude="\t",
    ) == "\t\t\t"


def test_strip_prefix():
    fmt = "%sbar"
    assert text_utils.strip_category(
        fmt % CHAR_BACKSPACE,
        text_utils.CATEGORY_CONTROL,
    ) == fmt % ""


def test_strip_suffix():
    fmt = "bar%s"
    assert text_utils.strip_category(
        fmt % CHAR_BACKSPACE,
        text_utils.CATEGORY_CONTROL,
    ) == fmt % ""


def test_strip_infix():
    fmt = "foo%sbar"
    assert text_utils.strip_category(
        fmt % CHAR_BACKSPACE,
        text_utils.CATEGORY_CONTROL,
    ) == fmt % ""


@pytest.mark.parametrize(
    "char",
    [six.unichr(c) for c in six.moves.range(0x00, 0x1F)]
)
def test_strip_control_characters(char):
    text = "%sfoo%sbar%s" % (char, char, char)
    expect = "foobar"
    assert text_utils.strip_control_characters(text) == expect
