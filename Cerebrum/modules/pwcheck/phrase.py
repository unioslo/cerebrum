#!/usr/bin/env python2
# encoding: utf-8
#
# Copyright 2003-2015 University of Oslo, Norway
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
""" This module contains simple password phrase checks. """

from .common import PasswordNotGoodEnough, PasswordChecker


class CheckPhraseLengthMixin(PasswordChecker):

    """ Check passphrase length. """

    # Minimum length and error message
    _passphrase_min_length = 12
    _passphrase_min_length_error_fmt = ("Password must be at least %d"
                                        " characters.")

    # Maximum length and error message
    _passphrase_max_length = None
    _passphrase_max_length_error_fmt = ("Password must be at most %d"
                                        " characters.")

    def password_good_enough(self, passphrase):
        """ Check that passphrase length is within bounds. """
        super(CheckPhraseLengthMixin, self).password_good_enough(passphrase)

        if (self._passphrase_min_length is not None and
                self._passphrase_min_length > len(passphrase)):
            raise PasswordNotGoodEnough(
                self._passphrase_min_length_error_fmt %
                self._passphrase_min_length)

        if (self._passphrase_max_length is not None and
                self._passphrase_max_length > len(passphrase)):
            raise PasswordNotGoodEnough(
                self._passphrase_max_length_error_fmt %
                self._passphrase_max_length)


class CheckPhraseWordsMixin(PasswordChecker):

    """ Check number of words in passphrase. """

    # Minimum word count, length and error message
    _passphrase_min_words = 2
    _passphrase_min_word_length = 2
    _passphrase_min_words_error_fmt = ("Password must have at least %d words"
                                       " of length %d")

    def password_good_enough(self, passphrase):
        """ Check that passphrase contains enough long words.

        Passphrase will require at least `_passphrase_min_words' of length
        `_passphrase_min_word_length'.

        """
        super(CheckPhraseWordsMixin, self).password_good_enough(passphrase)

        wl = self._passphrase_min_word_length
        wds = self._passphrase_min_words
        if len([x for x in passphrase.split(" ")
                if len(x) >= wl]) < wds:
            raise PasswordNotGoodEnough(
                self._passphrase_min_words_error_fmt % (wds, wl))


class CheckPassphraseMixin(CheckPhraseWordsMixin, CheckPhraseLengthMixin):
    pass
