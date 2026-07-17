# encoding: utf-8
"""
Tests for mod:`Cerebrum.utils.textnorm`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import codecs
import io

import pytest
import six

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


@pytest.fixture
def nfc():
    return textnorm.UnicodeNormalizer('NFC', False)


def test_normalize_form_get(nfc):
    assert nfc.form == "NFC"


def test_normalize_form_set(nfc):
    nfc.form = "NFD"
    assert nfc.form == "NFD"


def test_normalize_form_invalid(nfc):
    with pytest.raises(ValueError):
        nfc.form = "NFE"


def test_normalize_form_del(nfc):
    del nfc.form
    assert nfc.form is None


def test_normalize_repr(nfc):
    expect = (
        "Cerebrum.utils.textnorm.UnicodeNormalizer("
        + repr(nfc.form) + ", codec=False)"
    )
    assert repr(nfc) == expect


def test_normalize_str(nfc):
    assert six.text_type(nfc) == nfc.form


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


def test_normalize_bytes():
    # Ref TODO in the textnorm module - should this rather cause an error?
    normalize = textnorm.UnicodeNormalizer("NFC")
    text = "blåbærøl"
    byte_input = text.encode("utf-8")
    assert normalize(byte_input) == text


@norm_params
def test_normalize_codec_compat(form, data, expect):
    normalize = textnorm.UnicodeNormalizer(form, codec=True)
    norm = normalize(data)
    assert norm == (expect, len(data))


@pytest.fixture
def utf8_codec():
    return codecs.lookup('utf-8')


def test_normalizing_codec_patch(utf8_codec):
    textnorm.NormalizingCodec.patch(utf8_codec.streamreader)
    textnorm.NormalizingCodec.patch(utf8_codec.streamwriter)


@norm_params
def test_normalizing_codec_wrap(utf8_codec, form, data, expect):

    @textnorm.NormalizingCodec.wrap(encode=form, decode=form)
    class FooCodec(codecs.Codec):

        def encode(self, input, errors='strict'):
            return utf8_codec.encode(input, errors)

        def decode(self, input, errors='strict'):
            return utf8_codec.decode(input, errors)

    codec = FooCodec()

    assert codec.encode(data)[0] == expect.encode(utf8_codec.name)
    assert codec.decode(data.encode(utf8_codec.name))[0] == expect


@norm_params
def test_normalizing_codec_read(utf8_codec, form, data, expect):
    reader = textnorm.NormalizingCodec.patch(utf8_codec.streamreader,
                                             decode=form)
    with reader(io.BytesIO(data.encode(utf8_codec.name))) as stream:
        assert stream.read() == expect


@norm_params
def test_normalizing_codec_write(utf8_codec, form, data, expect):
    norm_writer = textnorm.NormalizingCodec.patch(utf8_codec.streamwriter,
                                                  encode=form)
    with norm_writer(io.BytesIO()) as bytestream:
        bytestream.write(data)
        assert bytestream.getvalue() == expect.encode(utf8_codec.name)
