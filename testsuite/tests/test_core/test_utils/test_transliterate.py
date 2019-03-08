#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2018 University of Oslo, Norway
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
""" Tests for Cerebrum.utils.funcwrap function wrappers. """

from __future__ import unicode_literals, print_function

import pytest

from Cerebrum.utils import transliterate


@pytest.mark.parametrize("text,expect", [
    ('blåbærsyltetøy', 'blaabaersyltetoy'),
    ('ᕘƀář', 'foobar')
])
def test_transliterate_to_ascii(text, expect):
    assert transliterate.to_ascii(text) == expect


@pytest.mark.parametrize("text,expect", [
    ('blåbærsyltetøy', 'bl}b{rsyltet|y'),
    ('BLÅBÆRSYLTETØY', 'BL]B[RSYLTET\\Y')
])
def test_transliterate_to_iso646_60(text, expect):
    assert transliterate.to_iso646_60(text) == expect


@pytest.mark.parametrize("text,expect", [
    ('Jørnulf   Ævensen', 'jornulf aevensen'),
    (' Olaf---Sverre Magnus -  Håkon-', 'olaf-sverre magnus-haakon'),
    ('bl}b{rsyltet|y', 'blabarsyltetoy')
])
def test_transliterate_for_posix(text, expect):
    assert transliterate.for_posix(text) == expect


@pytest.mark.parametrize("text,expect", [
    ('ÆØÅ', 'AOA'),
    ('{|}', 'aoa'),
])
def test_transliterate_for_gecos(text, expect):
    assert transliterate.for_gecos(text) == expect
