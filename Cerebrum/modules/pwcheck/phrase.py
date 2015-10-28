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
    _passphrase_min_length_error_fmt = ("Password must be at least %d"
                                        " characters.")

    # Maximum length and error message
    _passphrase_max_length_error_fmt = ("Password must be at most %d"
                                        " characters.")

    def password_good_enough(self, passphrase,
                             skip_rigid_password_tests=False,
                             passphrase_min_length=12,
                             passphrase_max_length=None,
                             **kw):
        """ Check that passphrase length is within bounds. """
        super(CheckPhraseLengthMixin, self).password_good_enough(
            passphrase,
            skip_rigid_password_tests=skip_rigid_password_tests, **kw)

        if skip_rigid_password_tests:
            if (passphrase_min_length is not None and
                    passphrase_min_length > len(passphrase)):
                raise PasswordNotGoodEnough(
                    self._passphrase_min_length_error_fmt %
                    passphrase_min_length)

            if (passphrase_max_length is not None and
                    passphrase_max_length > len(passphrase)):
                raise PasswordNotGoodEnough(
                    self._passphrase_max_length_error_fmt %
                    passphrase_max_length)


class CheckPhraseWordsMixin(PasswordChecker):

    """ Check number of words in passphrase. """

    # Minimum word count, length and error message
    _passphrase_min_words_error_fmt = ("Password must have at least %d words"
                                       " of length %d")
    _passphrase_avg_error_fmt = ("Password words must be in average at least"
                                 " %s characters long")

    def password_good_enough(self, passphrase,
                             passphrase_min_words=None,
                             passphrase_min_word_length=None,
                             passphrase_avg_length=None,
                             skip_rigid_password_tests=False,
                             **kw):
        """ Check that passphrase contains enough long words.

        Passphrase will require at least `_passphrase_min_words' of length
        `_passphrase_min_word_length'.

        """
        super(CheckPhraseWordsMixin, self).password_good_enough(
            passphrase,
            skip_rigid_password_tests=skip_rigid_password_tests,
            **kw)
        if not skip_rigid_password_tests:
            return
        wl = passphrase_min_word_length or 0
        wds = passphrase_min_words or 0
        avg = passphrase_avg_length
        spl = passphrase.split(" ")
        if len([x for x in spl if len(x) >= wl]) < wds:
            raise PasswordNotGoodEnough(
                self._passphrase_min_words_error_fmt % (wds, wl))
        if avg and float(sum(map(len, spl)))/len(spl) < avg:
            raise PasswordNotGoodEnough(
                self._passphrase_avg_error_fmt % (avg,))


class CheckPassphraseMixin(CheckPhraseWordsMixin, CheckPhraseLengthMixin):
    pass