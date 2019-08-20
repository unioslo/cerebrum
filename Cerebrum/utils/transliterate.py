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
"""Utilities for text transliteration."""
from __future__ import unicode_literals

import itertools
import re

import unidecode

from Cerebrum.utils.textnorm import normalize_text


re_not_letter_digit_space_dash = re.compile(r'[^a-zA-Z0-9 -]')


def strip_not_letter_digit_space_dash(s):
    return re_not_letter_digit_space_dash.sub('', s)


def strip_non_ascii(s):
    return s.encode('ascii', 'ignore').decode('ascii')


def lower(s):
    return s.lower()


def normalize_whitespace_and_hyphens(s):
    """Normalize whitespace and hyphens:
    - only ordinary single spaces as whitespace
    - only one space or hyphen between words
    - no leading or trailing spaces/hyphens
    """
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r' ?-+ ?', '-', s)
    return s.strip(' -')


def norwegian_chars_to_single_ascii_letter(s):
    tr = dict(zip(
        'ÆØÅæøå',
        'AOAaoa'))
    return Translate(translate=tr)(s)


def norwegian_chars_to_iso646_60(s):
    """Convert Norwegian characters to their ISO 646-60 representation."""
    tr = dict(zip(
        'ÆØÅæøå',
        '[\\]{|}'))
    return Translate(translate=tr)(s)


def iso646_60_to_ascii(s):
    """Some names are stored in the database using ISO 646-60 encoding.
    This converts back to an ASCII representation...
    """
    tr = dict(zip(
        '[\\]{|}¿',
        # ÆØÅæøåø
        'AOAaoao'))
    return Translate(translate=tr)(s)


def preferred_transliterations(s):
    """Used to override any default transliterations in unidecode."""
    replace = {
        'Æ': 'Ae',
        'æ': 'ae',
        'Å': 'Aa',
        'å': 'aa',
        'Ð': 'Dh',
        'ð': 'dh',
    }
    return CharReplace(replace)(s)


class CharReplace(object):
    """ Replace characters with strings. """

    def __init__(self, *dicts):
        self.translate = dict()
        for d in (dict(d) for d in dicts):
            for k, v in d.items():
                self.translate[normalize_text(k)] = normalize_text(v)

    def get(self, c):
        """ Get replacement string for char ``c``. """
        return self.translate.get(c, c)

    def __call__(self, string):
        return ''.join(map(self.get, iter(string)))


class Translate(object):
    """ Replace characters with characters. """

    def __init__(self, translate):
        translate = dict((ord(f), ord(t))
                         for f, t in (translate or dict()).items())
        self.translate = translate

    def __call__(self, string):
        return string.translate(self.translate)


class TranslateForEncoding(object):
    """
    Only transliterate unsupported characters in a given encoding.

    This callable will attempt to encode a given string using a given encoding,
    and transliterate any unsupported substrings using a given callable.

    The result should be a transliterated unicode object that should be
    possible to encode in the given encoding without errors.
    """
    def __init__(self, encoding, handle_unsupported):
        """
        :param encoding:
            the encoding to target
        :param handle_unsupported:
            a function / chain to transliterate unsupported substrings.
        """
        assert callable(handle_unsupported)
        self.encoding = encoding
        self.transliterate = handle_unsupported

    def _iter_substrings(self, string):
        # Cycle the unicode through the given codec to figure out which
        # characters can be encoded.
        encoded = string.encode(self.encoding,
                                errors='replace').decode(self.encoding)
        # Find sequences of characters that have been replaced, and
        # transliterate them using the given transliterate callable.
        for is_supported, pairs in itertools.groupby(
                zip(string, encoded),
                key=lambda pair: pair[0] == pair[1]):
            substring = ''.join(pair[0] for pair in pairs)
            if is_supported:
                yield substring
            else:
                yield self.transliterate(substring)

    def __call__(self, string):
        return ''.join(self._iter_substrings(string))


class Chain(object):
    """ Chain callables. """

    def __init__(self, *transformers):
        assert all(callable(x) for x in transformers)
        self.transformers = list(transformers)

    def __call__(self, value):
        for transformer in self.transformers:
            value = transformer(value)
        return value


to_ascii = Chain(
    normalize_text,
    preferred_transliterations,
    unidecode.unidecode,
    strip_non_ascii
)

to_iso646_60 = Chain(
    normalize_text,
    norwegian_chars_to_iso646_60,
    to_ascii)

for_gecos = Chain(
    normalize_text,
    norwegian_chars_to_single_ascii_letter,
    iso646_60_to_ascii,
    preferred_transliterations,
    unidecode.unidecode,
    strip_not_letter_digit_space_dash,
    normalize_whitespace_and_hyphens
)

for_posix = Chain(
    normalize_text,
    iso646_60_to_ascii,
    preferred_transliterations,
    unidecode.unidecode,
    strip_not_letter_digit_space_dash,
    normalize_whitespace_and_hyphens,
    lower
)

for_email_local_part = Chain(
    normalize_text,
    norwegian_chars_to_single_ascii_letter,
    iso646_60_to_ascii,
    preferred_transliterations,
    unidecode.unidecode,
    lower,
    strip_non_ascii
)


def for_encoding(encoding):
    """
    Transliterate text for a given encoding, with fallback to ascii for
    unsupported characters.

    This transliteration is typically good for exports where the encoding is
    configurable, and we want a best-effort match to the target encoding.
    """
    _to_ascii = Chain(
        preferred_transliterations,
        unidecode.unidecode_expect_nonascii,
        strip_non_ascii)
    return Chain(
        # TODO: NFC usually encodes better in iso8859 variants (and probably
        # most 8 bit charsets?). If we run into problems in weird charsets, we
        # may want to make normalizing optional, or allow other normalization
        # forms.
        normalize_text,
        TranslateForEncoding(encoding, _to_ascii))
