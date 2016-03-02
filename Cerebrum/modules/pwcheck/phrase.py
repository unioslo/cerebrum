#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2016 University of Oslo, Norway
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

from .common import pwchecker, PasswordChecker


@pwchecker('phrase_length')
class CheckPhraseLength(PasswordChecker):
    """ Check passphrase length. """

    # Minimum length and error message
    _min_length_error = ("Password must be at least %d characters.")

    # Maximum length and error message
    _max_length_error = ("Password must be at most %d characters.")

    def __init__(self, min_length=12, max_length=None):
        self.min_length = min_length
        self.max_length = max_length
        if not max_length:
            self._requirement = "Must be at least %d and at most %d characters." % (min_length, max_length)
        else:
            self._requirement = "Must be at least %d characters." % min_length

    def check_password(self, passphrase, account=None):
        """ Check that passphrase length is within bounds. """
        if (self.min_length is not None and
                self.min_length > len(passphrase)):
            return [self._min_length_error % self.min_length]

        if (self.max_length is not None and
                self.max_length > len(passphrase)):
            return [self._max_length_error % self.max_length]


@pwchecker('phrase_num_words')
class CheckPhraseWords(PasswordChecker):
    """ Check number of words in passphrase. """

    def __init__(self, min_words=None, min_word_length=None):
        self.min_words = min_words
        self.min_word_length = min_word_length
        if not min_word_length:
            self._requirement = "Must contain at least %d words." % min_words
        else:
            self._requirement = "Must contain at least %d words of length %d." % (min_words, min_word_length)

    def check_password(self, passphrase, account=None):
        """ Check that passphrase contains enough long words. """
        wl = self.min_word_length or 0
        wds = self.min_words or 0
        spl = passphrase.split(" ")
        if len([x for x in spl if len(x) >= wl]) < wds:
            return ("Password must have at least %d words"
                    " of length %d") % (wds, wl)


@pwchecker('phrase_avg_word_length')
class CheckPhraseAverageWordLength(PasswordChecker):
    """ Check number of words in passphrase. """

    def __init__(self, avg_length=0):
        self.avg_length = avg_length
        self._requirement = "Words must be in average at least %d characters long." % avg_length

    def check_password(self, passphrase, account=None):
        """ Check that passphrase contains enough long words in average. """
        avg = self.avg_length
        spl = passphrase.split(" ")
        if avg and float(sum(map(len, spl))) / len(spl) < avg:
            return ("Password words must be in average at least"
                    " %s characters long") % (avg,)
