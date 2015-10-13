#!/usr/bin/env python
# encoding: latin-1
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
import cereconf

from Cerebrum.modules.pwcheck.common import PasswordNotGoodEnough
from Cerebrum.modules.pwcheck.phrase import CheckPassphraseMixin


class HiHPasswordCheckerMixin(CheckPassphraseMixin):

    _passphrase_min_words = 2
    _passphrase_min_word_length = 2
    _passphrase_min_words_error_fmt = ("For få ord i passordet (minst %d"
                                       "ord på %d tegn")

    _passphrase_min_length = 12
    _passphrase_min_length_error_fmt = ("Passord må ha minst %d tegn")

    _passphrase_max_length = None
    _passphrase_max_length_error_fmt = "%r"

    def password_good_enough(self, passphrase, **kw):
        """Perform a number of checks on a password to see if it is good
        enough.

        HiH has the following rules:

        - Characters in the passphrase are either letters or whitespace.
        - The automatically generated password has a minimum of 12
          characters and 2 words (one space)
        - The user supplied passwords have a minimum of 12
          characters. There is no maximum (well, there is in the db
          schema, but this is irrelevant in the passwordchecker).
        """
        for char in passphrase:
            if not (char.isalpha() or char in 'æøåÆØÅ '):
                raise PasswordNotGoodEnough(
                    "Vennligst ikke bruk andre tegn enn bokstaver og blank.")

        super(HiHPasswordCheckerMixin, self).password_good_enough(passphrase,
                                                                  **kw)
        # Super checks length and words
