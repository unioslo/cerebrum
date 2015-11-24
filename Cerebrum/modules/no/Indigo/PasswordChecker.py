#!/usr/bin/env python
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

import cerebrum_path

from Cerebrum.modules.pwcheck.common import PasswordNotGoodEnough
from Cerebrum.modules.pwcheck.common import PasswordChecker
from Cerebrum.modules.pwcheck.simple import CheckCharSeqMixin
from Cerebrum.modules.pwcheck.simple import CheckRepeatedPatternMixin
from Cerebrum.modules.pwcheck.simple import CheckUsernameMixin
from Cerebrum.modules.pwcheck.history import PasswordHistoryMixin
from Cerebrum.modules.pwcheck.phrase import CheckPassphraseMixin


class _RepeatedPattern(CheckRepeatedPatternMixin, PasswordChecker):
    pass


class _CharSequence(CheckCharSeqMixin, PasswordChecker):
    pass


class OfkPasswordCheckerMixin(CheckUsernameMixin,
                              PasswordHistoryMixin):

    # This is a bit hackish, because we want to translate errors,
    # and we DONT want to re-implement all the checks...

    def password_good_enough(self, fullpasswd, **kw):
        """Perform a number of checks on a password to see if it is good
        enough.

        Øfk has the following rules:

        - Passwords must have minimum 8 character
        - 2 of the characters are digits
        - 6 of the characters are letters (upper/lower case mix)
        """

        num_digits = 0
        num_chars_lower = 0
        num_chars_upper = 0

        for char in fullpasswd:
            if not (char.isalpha() or char.isdigit()) or char == '$':
                raise PasswordNotGoodEnough(
                    "Vennligst ikke bruk andre tegn enn bokstaver og blank.")

        # Check that the password is long enough.
        if len(fullpasswd) < 8:
            raise PasswordNotGoodEnough("Passord må ha minst 8 tegn.")

        # Reversed patterns: abccba abcddcba
        try:
            pattern = _RepeatedPattern(self._db)
            pattern.password_good_enough(fullpasswd, **kw)
        except PasswordNotGoodEnough:
            raise PasswordNotGoodEnough(
                "Ikke bruk gjentagende grupper av tegn"
                " (eksempel: ikke 'abcabcabc').")

        # Check that the characters in the password are not a sequence
        try:
            sequence = _CharSequence(self._db)
            sequence.password_good_enough(fullpasswd, **kw)
        except PasswordNotGoodEnough:
            raise PasswordNotGoodEnough(
                "Ikke bruk tegn i alfabetisk rekkefølge"
                " (eksempel: ikke 'abcdef').")

        # Check organisation-specific rules
        for c in fullpasswd:
            if c.isdigit():
                num_digits = num_digits + 1
            elif c.islower():
                num_chars_lower = num_chars_lower + 1
            else:
                num_chars_upper = num_chars_upper + 1

        if not (num_digits >= 2
                and num_chars_lower > 0
                and num_chars_upper > 0):
            raise PasswordNotGoodEnough(
                "Passordkombinasjonen er ikke bra nok, vennligst prøv igjen.")

        try:
            super(OfkPasswordCheckerMixin,
                  self).password_good_enough(fullpasswd, **kw)
        except PasswordNotGoodEnough, e:
            if "username" in str(e):
                raise PasswordNotGoodEnough(
                    "Ikke la brukernavnet være en del av passordet.")
            if "similar" in str(e):
                raise PasswordNotGoodEnough(
                    "Det nye passordet var for likt det gamle."
                    " Velg et nytt ett.")
            raise


class GiskePasswordCheckerMixin(CheckPassphraseMixin):

    """Perform a number of checks on a password to see if it is good
    enough.

    Giske has the following rules:

    - Characters in the passphrase are either letters or whitespace.
    - The automatically generated password has a minimum of 14
      characters and 2 words; and a maximum of 20 characters.
    - The automatically generated passwords are generated out of a
      'child-friendly' dictionary (both nynorsk and bokmål).
    - The user supplied passwords have a minimum of 14
      characters. There is no maximum (well, there is in the db
      schema, but this is irrelevant in the passwordchecker).
    """

    _passphrase_min_words = 3
    _passphrase_min_word_length = 2
    _passphrase_min_words_error_fmt = ("For få ord i passordet (minst %d"
                                       "ord på %d tegn")

    _passphrase_min_length = 14
    _passphrase_min_length_error_fmt = ("Passord må ha minst %d tegn")

    _passphrase_max_length = None
    _passphrase_max_length_error_fmt = "%r"
