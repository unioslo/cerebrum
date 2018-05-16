# coding: utf-8
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
# Copyright 2002-2015 University of Oslo, Norway
""" This module contains unicode normalization utils. """
from __future__ import print_function

import codecs
import unicodedata

import six

NORMALIZATION_FORMS = ('NFC', 'NFKC', 'NFD', 'NFKD')
DEFAULT_FORM = 'NFC'


@six.python_2_unicode_compatible
class UnicodeNormalizer(object):
    """ Unicode normalizer function factory.

    Create a callable object that normalizes unicode text according to one of
    the normalization forms.

    Usage:

    >>> normalize = UnicodeNormalizer('NFC')
    >>> normalize(u'\N{ANGSTROM SIGN}')
    u'\cx5'
    >>> normalize.codec = True
    >>> normalize(u'\N{ANGSTROM SIGN}')
    (u'\xc5', 1)

    """

    def __init__(self, form=DEFAULT_FORM, codec=False):
        """
        :param str form:
            Choice of normalization form, check `NORMALIZATION_FORMS` for valid
            input.
        :param bool codec:
            Whether to be compatible with `Codec.encode` and `Codec.decode`,
            i.e. return number of processed characters in the result.
        """
        if form:
            self.form = form
        self.codec = codec

    @property
    def form(self):
        """ unicode normalization form """
        try:
            return self.__form
        except AttributeError:
            return None

    @form.setter
    def form(self, form):
        if form not in NORMALIZATION_FORMS:
            raise ValueError("Invalid normalization form")
        self.__form = form

    @form.deleter
    def form(self):
        self.__form = None

    def __repr__(self):
        return (
            '{0.__class__.__name__}({0.form!r}, codec={0.codec!r})'
        ).format(self)

    def __str__(self):
        return six.text_type(self.form)

    def __call__(self, input, errors='strict'):
        """ normalize unicode input.

        If `self.codec` is set to true, this method is `codecs.Codec` api
        method compatible (`encode`, `decode`).

        :param unicode input:
            The unicode input string to normalize.
            Note that the built-in `input` is shadowed here. This is because
            codecs.Codec calls this argument input.

        :param str errors:
            encode/decode error handling. Note that we don't actually use this,
            it's only for compatibility with `codecs.Codec`
        """

        # TODO: How should we handle non-unicode input?
        if isinstance(input, bytes):
            input = six.text_type(input)
        #     raise TypeError(
        #         "normalize argument must be {0}, not {1}".format(
        #             six.text_type.__name__, type(input).__name__))

        num = len(input)
        norm = unicodedata.normalize(self.form, input) if self.form else input

        if self.codec:
            return norm, num
        else:
            return norm


normalize = UnicodeNormalizer()


class NormalizingCodec(codecs.Codec, object):
    """ A mixin that can decorate actual codecs and ensure normalization.

    This class is a bit odd, as it tries to be an old-style class mixin that
    overloads the parent class methods.

    Example:

        import codecs

        codec_info = codecs.lookup('utf-8')
        NormalizingUtf8Reader = NormalizingCodec.patch(codec_info.streamreader,
                                                       decode='NFC')
    """
    __slots__ = ('_encode_form', '_decode_form')

    _encode_form = UnicodeNormalizer(None, True)
    _decode_form = UnicodeNormalizer(None, True)

    def encode(self, input, errors='strict'):
        encoded, num = self._encode_form(input, errors)
        try:
            encoded, _ = super(NormalizingCodec, self).encode(encoded, errors)
        except NotImplementedError:
            pass
        return encoded, num

    def decode(self, input, errors='strict'):
        try:
            decoded, num = super(NormalizingCodec, self).decode(input, errors)
            decoded, _ = self._decode_form(decoded)
        except NotImplementedError:
            decoded, num = self._decode_form(input)
        return decoded, num

    @classmethod
    def patch(cls, real_codec, encode=None, decode=None):
        """ Factory for adding unicode normalization to a codec class.

        Example:

            import encodings.latin1

            NormLatin1Codec = NormalizingCodec.patch(
                encodings.latin1.Codec,
                encode='NFC',
                decode='NFD')

        :param type real_codec:
            The codecs.Codec subclass that we're adding normalization to.
        :param str encode:
            A normalization form to use before encode (disabled if `None`)
        :param str decode:
            A normalization form to use after decode (disabled if `None`)

        :return type:
            Returns a subclass of this class and the codec.
        """
        name = str(real_codec).split('.')[-1]

        # Sigh, multiple inheritance with mixed old-style and new-style objects
        # is hard. Making the wrapped class into a new-style class seems to be
        # the best way to solve this
        real_codec = type('_{0}'.format(name), (real_codec, object), {})

        # Make a copy of `cls` that inherits from `real_codec`, with
        # normalization forms set to the `encoding` and `decoding` values.
        return type('NormalizingCodec_{0}'.format(name),
                    (cls, real_codec, object),
                    dict(_encode_form=UnicodeNormalizer(encode, True),
                         _decode_form=UnicodeNormalizer(decode, True)))

    @classmethod
    def wrap(cls, encode=None, decode=None):
        """ Returns a decorator that runs `patch` on codec classes.

        Example:

            import codecs

            @NormalizingCodec.wrap(decode='NFC')
            class MyCodec(codecs.Codec):
                ...

        :return callable:
            Returns a function that takes a codec class as argument, and
            returns a patched version with unicode normalization (see `patch`).
        """
        def wrapper(real_codec):
            return cls.patch(real_codec, encode=encode, decode=decode)
        return wrapper


def normalize_stream(stream,
                     encoding='ascii',
                     errors='strict',
                     normalize=None):
    """ Get a StreamReaderWriter with a given encoding and normalization form.

    :param encoding: The stream encoding
    :param errors: The encode/decode error handling
    :param normalize: The text normalization form

    :return codecs.StreamReaderWriter:
        Returns a stream that encodes/decodes and normalizes all text data.
    """
    encoder, decoder, Reader, Writer = codecs.lookup(encoding)
    Reader = NormalizingCodec.patch(Reader, decode=normalize)
    Writer = NormalizingCodec.patch(Writer, encode=normalize)
    return codecs.StreamReaderWriter(stream, Reader, Writer, errors=errors)


def normalize_text(value):
    """ Turns a value into an normalized unicode object. """
    return normalize(six.text_type(value))


def _main(inargs=None):
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="re-encode test")
    parser.add_argument(
        '-f',
        dest='decode',
        default='utf-8',
        help="input encoding")
    parser.add_argument(
        '-t',
        dest='encode',
        default='utf-8',
        help="output encoding")
    parser.add_argument(
        '-F',
        dest='decode_form',
        default=None,
        choices=NORMALIZATION_FORMS,
        help="input normalization")
    parser.add_argument(
        '-T',
        dest='encode_form',
        default=None,
        choices=NORMALIZATION_FORMS,
        help="output normalization")
    parser.add_argument(
        'infile',
        nargs='?',
        type=argparse.FileType(mode='r'),
        default=sys.stdin)
    parser.add_argument(
        'outfile',
        nargs='?',
        type=argparse.FileType(mode='w'),
        default=sys.stdout)

    args = parser.parse_args(inargs)

    with normalize_stream(
            args.infile,
            encoding=args.decode,
            normalize=args.decode_form) as instream:
        with normalize_stream(
                args.outfile,
                encoding=args.encode,
                normalize=args.encode_form) as outstream:
            outstream.write(instream.read())


if __name__ == '__main__':
    _main()
