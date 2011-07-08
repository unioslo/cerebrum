#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2003, 2007 University of Oslo, Norway
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

import re
from Cerebrum.modules import PasswordChecker as DefaultPasswordChecker
from Cerebrum.modules.PasswordChecker import PasswordGoodEnoughException


# The error messages are in Norwegian, since the end-users are likely to
# prefer it.
msgs = DefaultPasswordChecker.msgs
msgs.update({
    'invalid_char':
    """Vennligst ikke bruk andre tegn enn bokstaver og blank.""",
    'atleast12':
    """Passord må ha minst 14 tegn.""",
    'atleast8':
    """Passord må ha minst 8 tegn.""",
    'sequence_keys':
    """Ikke bruk de samme tegn om igjen etter hverandre.""",
    'was_like_old':
    """Det nye passordet var for likt det gamle. Velg et nytt ett.""",
    'repetitive_sequence':
    """Ikke bruk gjentagende grupper av tegn (eksempel: ikke 'abcabcabc').""",
    'sequence_alphabet':
    """Ikke bruk tegn i alfabetisk rekkefølge (eksempel: ikke 'abcdef').""",
    'uname_in_password':
    """Ikke la brukernavnet være en del av passordet.""",
    'bad_password':
    """Passordkombinasjonen er ikke bra nok, vennligst prøv igjen.""",
})


class HiHPasswordChecker(DefaultPasswordChecker.PasswordChecker):

    def goodenough(self, account, fullpasswd, uname=None):
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

        for char in fullpasswd:
            if not (char.isalpha() or char in 'æøåÆØÅ '):
                raise PasswordGoodEnoughException(msgs['invalid_char'])

        # Check that the password is long enough.
        if len(fullpasswd) < 12:
            raise PasswordGoodEnoughException(msgs['atleast11'])

        # at least 2 words, each word at least 2 characters
        if len([x for x in fullpasswd.split(" ") if len(x) >= 2]) < 2:
            raise PasswordGoodEnoughException("For få ord i passordet")

        return True


if __name__ == "__main__":
    from Cerebrum.Account import Account
    from Cerebrum.Utils import Factory
    db = Factory.get("Database")()
    pc = HiHPasswordChecker(db)
    account = Factory.get("Account")(db)

    for candidate in ("åæålllkkk34", # invalid chars (disabled 2007-03-28)
                      "hYt87",              # too short
                      "ooooooooo",    # all alike
                      "abcabcabcabcabc",     # repeating pattern
                      "abccba9fo",      # repeating pattern
                      "jashod78",      # username (fake)
                      "abcdefghijklmnopqr",  # sequence
                      "asdfghjklzxcvbnm",    # allowed 
                      "qwertyuiopasdfghj",   # allowed
                      "qwerty asdfghj zxcv", # keyboard sequence
                      "aaaaaaaaaacccccccc",  # repeating chars
                      "43HIaHeD"): # valid
        try:
            pc.goodenough(None, candidate, "this is a user")
            print "candidate: <%s>: ok!" % (candidate,)
        except PasswordGoodEnoughException, val:
            print "candidate: <%s>: failed: %s" % (candidate, val)
