# -*- coding: utf-8 -*-
"""
Tests for mod:`Cerebrum.utils.transliterate`
"""
from __future__ import (
    absolute_import,
    division,
    unicode_literals,
    print_function,
)

import pytest

from Cerebrum.utils import transliterate


@pytest.mark.parametrize(
    "text, expect",
    [
        ('blåbærsyltetøy', 'blaabaersyltetoy'),
        ('ᕘƀář', 'foobar'),
    ],
)
def test_transliterate_to_ascii(text, expect):
    assert transliterate.to_ascii(text) == expect


@pytest.mark.parametrize(
    "text, expect",
    [
        ('blåbærsyltetøy', 'bl}b{rsyltet|y'),
        ('BLÅBÆRSYLTETØY', 'BL]B[RSYLTET\\Y'),
    ],
)
def test_transliterate_to_iso646_60(text, expect):
    assert transliterate.to_iso646_60(text) == expect


@pytest.mark.parametrize(
    "text, expect",
    [
        ('Jørnulf   Ævensen', 'jornulf aevensen'),
        (' Olaf---Sverre Magnus -  Håkon-', 'olaf-sverre magnus-haakon'),
        ('bl}b{rsyltet|y', 'blabarsyltetoy'),
    ],
)
def test_transliterate_for_posix(text, expect):
    assert transliterate.for_posix(text) == expect


@pytest.mark.parametrize(
    "text, expect",
    [
        ('ÆØÅ', 'AOA'),
        ('{|}', 'aoa'),
    ],
)
def test_transliterate_for_gecos(text, expect):
    assert transliterate.for_gecos(text) == expect


ENCODING_TESTS = [
    # Check that compatible letters remains
    (
        'utf-8',
        'Blåbær\N{LATIN SMALL LETTER S WITH DOT ABOVE}aft',
        'Blåbærṡaft',
     ),
    (
        'iso8859-1',
        'Blåbær\N{LATIN SMALL LETTER S WITH DOT ABOVE}aft',
        'Blåbærsaft',
    ),
    (
        'ascii',
        'Blåbær\N{LATIN SMALL LETTER S WITH DOT ABOVE}aft',
        'Blaabaersaft',
    ),
    # Check that NFD is normalized
    (
        'latin-1',
        'Bla\N{COMBINING RING ABOVE}bærsaft',
        'Blåbærsaft',
    ),
]


@pytest.mark.parametrize(
    "encoding, text, expect",
    ENCODING_TESTS,
    ids=[t[0] for t in ENCODING_TESTS],
)
def test_transliterate_for_encoding(encoding, text, expect):
    trans = transliterate.for_encoding(encoding)
    assert trans(text) == expect
