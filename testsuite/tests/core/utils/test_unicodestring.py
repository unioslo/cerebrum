# -*- coding: utf-8 -*-

# Copyright 2020 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

from __future__ import unicode_literals

import pytest
import six

from Cerebrum.utils.unicodestring import (
    control,
    replace_category,
    strip_category,
    strip_control_characters,
)


control_characters = six.moves.range(0x00, 0x1F)
bs = unichr(0x08)

categories = (control,)


@pytest.mark.parametrize("category", categories)
@pytest.mark.parametrize("invalid_type", (None, 42, True, [], (), {}, object()))
def test_replace_invalid_types(category, invalid_type):
    with pytest.raises(TypeError):
        replace_category(invalid_type, category, "�")


@pytest.mark.parametrize("category", categories)
@pytest.mark.parametrize("invalid_type", (None, 42, True, [], (), {}, object()))
def test_strip_invalid_types(category, invalid_type):
    with pytest.raises(TypeError):
        strip_category(invalid_type, category)


def test_replace_invalid_category():
    with pytest.raises(ValueError) as excinfo:
        replace_category("foo", "invalid_category", "�")
    assert "Invalid code point label" in str(excinfo.value)


def test_strip_invalid_category():
    with pytest.raises(ValueError) as excinfo:
        strip_category("foo", "invalid_category")
    assert "Invalid code point label" in str(excinfo.value)


@pytest.mark.parametrize("category", categories)
def test_replace_empty_string(category):
    assert replace_category("", category, "�") == ""
    assert replace_category(" ", category, "�") == " "


@pytest.mark.parametrize("category", categories)
def test_strip_empty_string(category):
    assert strip_category("", category) == ""
    assert strip_category(" ", category) == " "


@pytest.mark.parametrize(
    "n,expected_n", ((-1, 3), (0, 0), (1, 1), (2, 2), (3, 3), (4, 3))
)
def test_replace_maxreplace(n, expected_n):
    s = bs * 3
    expected = "�" * expected_n
    while len(expected) < len(s):
        expected += bs
    assert replace_category(s, control, "�", maxreplace=n) == expected


@pytest.mark.parametrize(
    "n,expected_n", ((-1, 0), (0, 3), (1, 2), (2, 1), (3, 0), (4, 0))
)
def test_strip_maxstrip(n, expected_n):
    assert len(strip_category(bs * 3, control, maxstrip=n)) == expected_n


def test_replace_exclude():
    assert replace_category("\t", control, "�", exclude="\n") == "�"
    assert replace_category("\t\r\n", control, "�", exclude="\n") == "��\n"
    assert replace_category("\t\r\n", control, "�", exclude="\t\n") == "\t�\n"
    assert replace_category("\t\t\t\r\n", control, "�", exclude="\t") == "\t\t\t��"


def test_strip_exclude():
    assert strip_category("\t", control, exclude="\n") == ""
    assert strip_category("\t\r\n", control, exclude="\n") == "\n"
    assert strip_category("\t\r\n", control, exclude="\t\n") == "\t\n"
    assert strip_category("\t\t\t\r\n", control, exclude="\t") == "\t\t\t"


@pytest.mark.parametrize("rune", map(unichr, control_characters))
def test_strip_control_characters(rune):
    assert strip_control_characters(rune) == ""
    assert strip_control_characters(rune) == strip_category(rune, control)


@pytest.mark.parametrize("category,code_point", ((control, bs),))
def test_replace_mixed(category, code_point):
    assert replace_category("foo%c" % code_point, category, "�") == "foo�"
    assert replace_category("foo%cbar" % code_point, category, "�") == "foo�bar"
    assert replace_category("%cbar" % code_point, category, "�") == "�bar"


@pytest.mark.parametrize("category,code_point", ((control, bs),))
def test_strip_mixed(category, code_point):
    assert strip_category("foo%c" % code_point, category) == "foo"
    assert strip_category("foo%cbar" % code_point, category) == "foobar"
    assert strip_category("%cbar" % code_point, category) == "bar"
