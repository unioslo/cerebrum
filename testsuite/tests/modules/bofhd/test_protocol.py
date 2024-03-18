# -*- coding: utf-8 -*-

# Copyright 2020 University of Oslo
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

import pytest
import six

from Cerebrum.modules.bofhd.protocol import sanitize


@pytest.mark.parametrize("s", ("foo", six.text_type("foo")))
def test_sanitize_string_coercion(s):
    assert isinstance(sanitize(s), six.text_type)


@pytest.mark.parametrize("rune", six.moves.range(0x00, 0x1F))
def test_sanitize_strip_control_characters(rune):
    # skip TAB, CR, and LF
    if rune not in (0x09, 0x0A, 0x0D):
        assert sanitize(unichr(rune)) == six.text_type("")


@pytest.mark.parametrize("actual,expected", (
    ("foo\x08", "foo"),
    ("foo\x08bar",  "foobar"),
    ("\x08bar", "bar"),
))
def test_sanitize_mixed_control_characters(actual, expected):
    assert sanitize(actual) == expected


@pytest.mark.parametrize("rune", ("\t", "\r", "\n"))
def test_sanitize_preserve_line_feeds(rune):
    assert sanitize(rune) == rune


@pytest.mark.parametrize("seq", (["foo", ["bar"]], ("foo", ("bar",))))
def test_sanitize_collection(seq):
    assert sanitize(seq) == [six.text_type("foo"), [six.text_type("bar")]]


def test_sanitize_dict():
    assert sanitize({u"foo": {u"bar": "baz"}}) == {u"foo": {u"bar": u"baz"}}


@pytest.mark.parametrize("t", (None, True, object()))
def test_sanitize_other_types(t):
    assert type(sanitize(t)) == type(t)
    assert sanitize(t) == t
