#!/usr/bin/env python
# encoding: utf-8
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

import codecs
import io
import pytest

from Cerebrum.utils import textnorm


@pytest.mark.parametrize('form', [None, 'NFC', 'NFD', 'NFKC', 'NFKD'])
def test_normalize_init(form):
    normalize = textnorm.UnicodeNormalizer(form)
    assert normalize.form == form
    assert normalize.codec is False


def test_normalize_codec_init():
    codec = textnorm.UnicodeNormalizer('NFC', True)
    assert codec.codec is True


def test_normalize_invalid_form():
    with pytest.raises(ValueError):
        textnorm.UnicodeNormalizer('NFE')


# tuples with (testname, normalization form, input, expected output)
# input/output from UAX #15
_norm_tests = [
    ('noop', None, '\N{ANGSTROM SIGN}', '\N{ANGSTROM SIGN}'),
    ('nfc angstrom', 'NFC',
     '\N{ANGSTROM SIGN}',
     '\N{LATIN CAPITAL LETTER A WITH RING ABOVE}'),
    ('nfd angstrom', 'NFD', '\N{ANGSTROM SIGN}', 'A\N{COMBINING RING ABOVE}'),
    ('nfc ohm', 'NFC', '\N{OHM SIGN}', '\N{GREEK CAPITAL LETTER OMEGA}'),
    ('nfd ohm', 'NFD', '\N{OHM SIGN}', '\N{GREEK CAPITAL LETTER OMEGA}'),
    ('nfc long s', 'NFC', '\u1e9b\u0323', '\u1e9b\u0323'),
    ('nfd long s', 'NFD', '\u1e9b\u0323', '\u017f\u0323\u0307'),
    ('nfkc long s', 'NFKC', '\u1e9b\u0323', '\u1e69'),
    ('nfkd long s', 'NFKD', '\u1e9b\u0323', 's\u0323\u0307'),
]

norm_params = pytest.mark.parametrize(
    "form,data,expect",
    [t[1:] for t in _norm_tests],
    ids=[t[0] for t in _norm_tests])


@norm_params
def test_normalize(form, data, expect):
    normalize = textnorm.UnicodeNormalizer(form)
    norm = normalize(data)
    assert norm == expect


@norm_params
def test_normalize_codec_compat(form, data, expect):
    normalize = textnorm.UnicodeNormalizer(form, codec=True)
    norm = normalize(data)
    assert norm == (expect, len(data))


@pytest.fixture
def Codec():
    return codecs.lookup('utf-8')


def test_normalizing_codec_patch(Codec):
    textnorm.NormalizingCodec.patch(Codec.streamreader)
    textnorm.NormalizingCodec.patch(Codec.streamwriter)


@norm_params
def test_normalizing_codec_wrap(Codec, form, data, expect):

    @textnorm.NormalizingCodec.wrap(encode=form, decode=form)
    class FooCodec(codecs.Codec):

        def encode(self, input, errors='strict'):
            return Codec.encode(input, errors)

        def decode(self, input, errors='strict'):
            return Codec.decode(input, errors)

    codec = FooCodec()

    assert codec.encode(data)[0] == expect.encode(Codec.name)
    assert codec.decode(data.encode(Codec.name))[0] == expect


@norm_params
def test_normalizing_codec_read(Codec, form, data, expect):
    Reader = textnorm.NormalizingCodec.patch(Codec.streamreader,
                                             decode=form)
    with Reader(io.BytesIO(data.encode(Codec.name))) as stream:
        assert stream.read() == expect


@norm_params
def test_normalizing_codec_write(Codec, form, data, expect):
    NormWriter = textnorm.NormalizingCodec.patch(Codec.streamwriter,
                                                 encode=form)
    with NormWriter(io.BytesIO()) as bytestream:
        bytestream.write(data)
        assert bytestream.getvalue() == expect.encode(Codec.name)
