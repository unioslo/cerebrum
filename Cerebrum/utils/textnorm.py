# coding: utf-8
#
# Copyright 2018-2026 University of Oslo, Norway
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
"""
Unicode normalization utils.

This module provides utilities for normalizing unicode texts, according to the
`Unicode Standard Annex #15 <https://unicode.org/reports/tr15/>`_.

All data in Cerebrum should be normalized to *NFC* before being stored in the
database, or before being compared with database values.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import codecs
import unicodedata

import six

from . import reprutils
from . import text_compat


NORMALIZATION_FORMS = ('NFC', 'NFKC', 'NFD', 'NFKD')
"""
Supported normalization forms.

This module supports all normalization forms specified by the Unicode
standard.
"""

DEFAULT_FORM = 'NFC'
"""
Default normalization form.

Cerebrum uses *NFC* as the default normalization form.  NFC is more compatible
with legacy encodings, and recommended for general text use in the Unicode
standard.
"""


@six.python_2_unicode_compatible
class UnicodeNormalizer(reprutils.ReprEvalMixin):
    r"""
    Unicode normalizer function factory.

    Create a callable object that normalizes unicode text according to one of
    the normalization forms.

    >>> normalize = UnicodeNormalizer('NFC')
    >>> normalize('\N{ANGSTROM SIGN}')
    '\xc5'
    >>> normalize.codec = True
    >>> normalize('\N{ANGSTROM SIGN}')
    ('\xc5', 1)

    """

    repr_module = True
    repr_args = ("form",)
    repr_kwargs = ("codec",)

    def __init__(self, form=DEFAULT_FORM, codec=False):
        """
        :param str form:
            Choice of normalization form.

            Must be one of the supported :data:`.NORMALIZATION_FORMS`.

        :param bool codec:
            :class:`codecs.Codec` compatibility.

            If this is true, the normalization call will include the number of
            processed characters in the result.  This allows the normalizer to
            be used as a mock codec.
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

    def __str__(self):
        return six.text_type(self.form)

    def __call__(self, input, errors='strict'):
        """
        Normalize unicode input.

        :param str input:
            The input string to normalize.

        :param str errors:
            encode/decode error handling.

            This argument is ignored - and only used for compatibility with
            codec encode/decode calls.

        :rtype: str or tuple[str, int]
        :returns:
            Returns the normalized text.

            If ``codec=True`` when creating this callable, the return value
            will be a tuple containing the normalized text, and the number of
            processed characters.  This allows the normalizer call to be used
            as a :class:`codecs.Codec` ``encode`` or ``decode`` method.

        """
        # Note that the built-in `input` is shadowed here. This is because
        # `codecs.Codec` calls this argument input.

        if isinstance(input, bytes):
            input = text_compat.to_text(input)

        num = len(input)
        norm = unicodedata.normalize(self.form, input) if self.form else input

        if self.codec:
            return norm, num
        else:
            return norm


normalize = UnicodeNormalizer()


class NormalizingCodec(codecs.Codec, object):
    """
    A mixin that can decorate actual codecs and ensure normalization.

    This class is a bit odd, as it tries to be an old-style class mixin that
    overloads the parent class methods.

    Example:
    ::

        import codecs

        codec_info = codecs.lookup('utf-8')
        NormalizingUtf8Reader = NormalizingCodec.patch(codec_info.streamreader,
                                                       decode='NFC')
    """
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
        """
        Factory for adding unicode normalization to a codec class.

        Example:
        ::

            import encodings.latin1
            NormLatin1Codec = NormalizingCodec.patch(
                encodings.latin1.Codec, encode='NFC', decode='NFD')

        :param type real_codec:
            The codecs.Codec subclass that we're adding normalization to.

        :param str encode:
            A normalization form to use before encode (disabled if `None`)

        :param str decode:
            A normalization form to use after decode (disabled if `None`)

        :rtype: type
        :returns:
            Returns a subclass of this class and the codec.
        """
        name = six.text_type(real_codec).split('.')[-1]
        real_name = text_compat.to_str("_{}".format(name))
        new_name = text_compat.to_str("NormalizingCodec_{}".format(name))

        # Sigh, multiple inheritance with mixed old-style and new-style objects
        # is hard. Making the wrapped class into a new-style class seems to be
        # the best way to solve this
        real_codec = type(real_name, (real_codec, object), {})

        # Make a copy of `cls` that inherits from `real_codec`, with
        # normalization forms set to the `encoding` and `decoding` values.
        return type(new_name,
                    (cls, real_codec, object),
                    dict(_encode_form=UnicodeNormalizer(encode, True),
                         _decode_form=UnicodeNormalizer(decode, True)))

    @classmethod
    def wrap(cls, encode=None, decode=None):
        """ Returns a decorator that runs `patch` on codec classes.

        Example:
        ::

            import codecs

            @NormalizingCodec.wrap(decode='NFC')
            class MyCodec(codecs.Codec):
                ...

        :rtype: callable
        :returns:
            Returns a decorator function.

            The decorator that can be used to *patch* an existing codec with
            normalization.  See :meth:`.patch` for more on this behaviour.
        """
        def wrapper(real_codec):
            return cls.patch(real_codec, encode=encode, decode=decode)
        return wrapper


def normalize_stream(stream,
                     encoding='ascii',
                     errors='strict',
                     normalize=None):
    """
    Get a StreamReaderWriter with a given encoding and normalization form.

    :param encoding: The stream encoding
    :param errors: The encode/decode error handling
    :param normalize: The text normalization form

    :rtype: codecs.StreamReaderWriter
    :returns:
        Returns a stream that encodes/decodes and normalizes all text data.
    """
    encoder, decoder, reader, writer = codecs.lookup(encoding)
    reader = NormalizingCodec.patch(reader, decode=normalize)
    writer = NormalizingCodec.patch(writer, encode=normalize)
    return codecs.StreamReaderWriter(stream, reader, writer, errors=errors)


def normalize_text(value):
    """ Turns a value into a normalized unicode object. """
    return normalize(six.text_type(value))


def _main(inargs=None):
    import argparse
    from . import file_stream

    default_codec = "utf-8"
    parser = argparse.ArgumentParser(
        description="Normalize and re-encode text",
    )
    parser.add_argument(
        '-f',
        dest='decode',
        default=default_codec,
        help="input file encoding (default: %(default)s)",
        metavar="codec"
    )
    parser.add_argument(
        '-t',
        dest='encode',
        default=default_codec,
        help="output file encoding (default: %(default)s)",
        metavar="codec"
    )
    parser.add_argument(
        '-F',
        dest='decode_form',
        default=None,
        choices=NORMALIZATION_FORMS,
        help="input normalization (default: no normalization)",
    )
    parser.add_argument(
        '-T',
        dest='encode_form',
        default=None,
        choices=NORMALIZATION_FORMS,
        help="output normalization (default: no normalization)",
    )
    parser.add_argument(
        'infile',
        nargs='?',
        default=file_stream.DEFAULT_STDIN_NAME,
    )
    parser.add_argument(
        'outfile',
        nargs='?',
        default=file_stream.DEFAULT_STDOUT_NAME,
    )

    args = parser.parse_args(inargs)

    with file_stream.get_input_context(args.infile,
                                       encoding=None) as instream:
        with normalize_stream(
                instream,
                encoding=args.decode,
                normalize=args.decode_form) as instream:
            text = instream.read()

    with file_stream.get_output_context(args.outfile,
                                        encoding=None) as outstream:
        with normalize_stream(
                outstream,
                encoding=args.encode,
                normalize=args.encode_form) as outstream:
            outstream.write(text)


if __name__ == '__main__':
    _main()
