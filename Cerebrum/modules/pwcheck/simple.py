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
""" This module contains simple password checks.

The CheckSimpleMixin class is an adoption of the old PasswordChecker class, and
used to check simple password constraints.

HISTORY
-------
This module was moved from Cerebrum.modules.PasswordChecker. For the old
structure of the dictionary checks, please see:

> commit 9a01d8b6ac93513a57ac8d6393de842939582f51
> Mon Jul 20 14:12:55 2015 +0200

"""

import cerebrum_path
import cereconf

import re
import operator

from Cerebrum.Errors import NotFoundError
from Cerebrum.Utils import Factory

from . import common


# TODO: Should we really disallow characters from passwords?
class CheckInvalidCharsMixin(common.PasswordChecker):

    """ Check for illegal characters in password string. """

    _password_illegal_chars = {
        '\0': "Password cannot contain the null character.",
        ' ': "Password cannot contain space.", }

    _password_illegal_regex = {
        r'[\200-\376]':
            "Password cannot contain 8-bit characters (e.g.  æøå).", }

    def password_good_enough(self, password, skip_rigid_password_tests=False,
                             **kw):
        """ Check that only valid characters are allowed. """
        super(CheckInvalidCharsMixin, self).password_good_enough(
            password, skip_rigid_password_tests=skip_rigid_password_tests, **kw)

        if skip_rigid_password_tests:
            return
        for char, err in self._password_illegal_chars.iteritems():
            if char in password:
                raise common.PasswordNotGoodEnough(err)

        for regex, err in self._password_illegal_regex.iteritems():
            if re.search(regex, password):
                raise common.PasswordNotGoodEnough(err)


class CheckLengthMixin(common.PasswordChecker):

    """ Check for minimum and maximum password length. """

    def password_good_enough(self, password,
                             password_min_length=8, password_max_length=None,
                             **kw):
        """Check the length of the password.

        The password must be at least _password_min_length long and at most
        _password_max_length long.

        """
        super(CheckLengthMixin, self).password_good_enough(password,
                                                           **kw)

        if (password_min_length is not None
                and len(password.strip()) < password_min_length):
            raise common.PasswordNotGoodEnough(
                "Password must be at least %d characters long." %
                password_min_length)

        if (password_max_length is not None
                and len(password) > password_max_length):
            raise common.PasswordNotGoodEnough(
                "Password must be at most %d characters long." %
                password_max_length)


# TODO: Can we get rid of this?
class CheckConcatMixin(common.PasswordChecker):

    """We disallow passwords like 'Camel*Toe'.

    (Passwords are pretty legit otherwise, except that they are
    essentially 2 dictionary words combined).

    TBD: Is this really a good idea? This check disallows passwords like
    'Hsy#Klj7', which is clearly completely insane, but will still allow
    'Camel**Toe' or 'CamelToe'.

    """

    def password_good_enough(self, password,
                             skip_rigid_password_tests=False,
                             **kw):
        """ This is insane. """
        super(CheckConcatMixin, self).password_good_enough(
            password,
            skip_rigid_password_tests=skip_rigid_password_tests,
            **kw)

        if not skip_rigid_password_tests:
            first_eight = password[0:8]

            if (re.search(r'^[A-Z][a-z]+[^A-Za-z0-9][A-Z][a-z]*$', first_eight)
                    or re.search(r'^[A-Z][a-z]+[^A-Za-z0-9][A-Z][a-z]*$',
                                 password)):
                raise common.PasswordNotGoodEnough(
                    "Password cannot contain two concatenated words.")


class CheckEntropyMixin(common.PasswordChecker):

    """ Adds a entropy check to password checker. """

    def password_good_enough(self, password,
                             skip_rigid_password_tests=False,
                             **kw):
        """ Check that a password use multiple character sets.

        The password must contain characters from at least three
        of the following sets:

          - lowecase
          - uppercase
          - digit
          - special char

        """

        super(CheckEntropyMixin, self).password_good_enough(
            password,
            skip_rigid_password_tests=skip_rigid_password_tests,
            **kw)

        if skip_rigid_password_tests:
            return
        # TODO: Write proper regex, so that we don't have to truncate the
        # password
        first_eight = password[0:8]

        good_try = variation = 0
        if re.search(r'[a-z]', first_eight):
            variation += 1
        if re.search(r'[A-Z][^A-Z]{7}', first_eight):
            # The only upper case character in the first 8 characters is in
            # position 1
            good_try += 1
        if re.search(r'[A-Z]', first_eight[1:8]):
            # Contains at least 1 upper case char in pos 1-8.
            variation += 1
        if re.search(r'[^0-9]{7}[0-9]', first_eight):
            # Only number (in the first eight chars), is the last char
            good_try += 1
        if re.search(r'[0-9]', first_eight[0:7]):
            # contains a number in the first 7 chars
            variation += 1
        if re.search(r'[A-Za-z0-9]{7}[^A-Za-z0-9]', first_eight):
            # Only non-alnum and non-digit is the last one.
            good_try += 1
        if re.search(r'[^A-Za-z0-9]', password[0:7]):
            # Must contain a non-alnum and non-digit char
            variation += 1

        if variation < 3:
            if good_try:
                raise common.PasswordNotGoodEnough(
                    "A password that only contains one uppercase letter,"
                    " must not have this as the first character."
                    " If the first 8 characters only contains one number or"
                    " special character, this must not be in position 8.")
            else:
                raise common.PasswordNotGoodEnough(
                    "The first eight characters of the password must contain"
                    " characters from at least three of the four following"
                    " character groups: Uppercase letters, lowercase letters,"
                    " numbers and special characters.")


class CheckCharSeqMixin(common.PasswordChecker):

    """ Check for sequences of related chars. """

    def password_good_enough(self, password, char_seq_length=3, **kw):
        """ Check for sequences of closely related characters. """
        super(CheckCharSeqMixin, self).password_good_enough(password, **kw)

        if isinstance(password, str):
            try:
                password = unicode(password, 'UTF-8')
            except UnicodeDecodeError:
                password = unicode(password, 'ISO-8859-1')
        passwd = password.lower()
        ordpw = map(ord, passwd)

        def find_adjacent_runs(seq):
            def fun(tot, elt):
                if tot and tot[-1][0] == elt:
                    tot[-1][1] += 1
                else:
                    tot.append([elt, 1])
                return tot
            return reduce(fun, seq, [])

        # A sequence of closely related ASCII characters.
        for diff, num in find_adjacent_runs(
                map(operator.sub, ordpw[1:], ordpw[:-1])):
            if diff in (-1, 1) and num >= char_seq_length:
                raise common.PasswordNotGoodEnough(
                    "Password cannot contain characters in alpabetical or"
                    " numerical order")

        # TODO: 'kbd' should probably try a number of typical layouts.
        # Rows may be of different lengths, but the same symbol CANNOT occur
        # more than once.
        keyboard_rows = (u"qwertyuiop[]",
                         u"qwertyuiopå",  # norwegian
                         u"asdfghjkl;'",
                         u"asdfghjkløæ",  # norwegian
                         u"zxcvbnm,./",
                         u"zxcvbnm,.-",   # norwegian
                         u"!@#$%^&*()_+|~",
                         u"§!\"#$%&/()=?",
                         u"-1234567890=\`",
                         u"å,.pyfgcrl'",  # dvorak
                         u"å;:pyfgcrl'",  # dvorak
                         u"aoeuidhtns-<",  # dvorak
                         u"øæqjkxbmwvz",  # dvorak
                         )

        for row in keyboard_rows:
            mapper = dict([(key, val+1) for val, key in enumerate(row)])
            pw = [mapper.get(x, -1) for x in passwd]
            runs = find_adjacent_runs(map(operator.sub, pw[1:], pw[:-1]))
            for diff, num in runs:
                if diff in (-1, 1) and num >= char_seq_length:
                    raise common.PasswordNotGoodEnough(
                        "Password cannot contain neighbouring keyboard keys")


class CheckRepeatedPatternMixin(common.PasswordChecker):

    """ Check for repeated patterns in password. """

    def password_good_enough(self, password, skip_rigid_password_tests=False,
                             **kw):
        """ Check for repeated sequences in the first eight chars. """
        super(CheckRepeatedPatternMixin, self).password_good_enough(
            password,
            skip_rigid_password_tests=skip_rigid_password_tests,
            **kw)

        if skip_rigid_password_tests:
            return

        # TODO: Clean up this check, and get rid of the trunc
        first_eight = password[0:8]
        repeat_err = common.PasswordNotGoodEnough(
            "Password cannot contain repeated sequences of characters.")

        # Repeated patterns: ababab, abcabc, abcdabcd
        if (re.search(r'^(..)\1\1', first_eight) or
                re.search(r'^(...)\1', first_eight) or
                re.search(r'^(....)\1', first_eight)):
            raise repeat_err

        # Reversed patterns: abccba abcddcba
        if (re.search(r'^(.)(.)(.)\3\2\1', first_eight) or
                re.search(r'^(.)(.)(.)(.)\4\3\2\1', first_eight)):
            raise repeat_err


class CheckUsernameMixin(common.PasswordChecker):

    """ Check for use of the username in the password. """

    def password_good_enough(self, password, **kw):
        """ Does the password contain the username? """
        super(CheckUsernameMixin, self).password_good_enough(password, **kw)
        name = getattr(self, 'account_name', None)
        if name is not None:
            self._check_uname_password(name, password)

    def _check_uname_password(self, name, passwd):
        # password cannot contain the username
        if name.lower() in passwd.lower():
            raise common.PasswordNotGoodEnough(
                "Password cannot contain your username")

        # password cannot contain the username reversed
        if name[::-1].lower() in passwd.lower():
            raise common.PasswordNotGoodEnough(
                "Password cannot contain your username in reverse")


class CheckOwnerNameMixin(common.PasswordChecker):

    """ Check for use of the account owners name in the password. """

    def password_good_enough(self, password, name_seq_len=5, **kw):
        super(CheckOwnerNameMixin, self).password_good_enough(password, **kw)

        if not hasattr(self, 'owner_id'):
            return

        if isinstance(password, str):
            try:
                password = unicode(password, 'UTF-8')
            except:
                password = unicode(password, 'ISO-8859-1')

        self._check_human_owner(self.owner_id, password, name_seq_len)

    def _check_human_owner(self, owner_id, password, seqlen):
        """Check if password is a variation of the owner's name."""
        # TODO: Should we not check the name of other owner types as well?
        #       E.g.: owner=group:foobarbaz, password=fooBARbaz

        # First, do we have a human owner at all?
        person = Factory.get("Person")(self._db)
        const = Factory.get("Constants")(self._db)
        try:
            person.find(owner_id)
        except NotFoundError:
            return
        # Which name to use? Let's grab the first full name we find
        # TODO: Why not check _ALL_ the names? What if there are multiple
        # `name_full' names, but they are different between source systems?
        for row in person.get_all_names():
            if row["name_variant"] == const.name_full:
                name = row["name"]
                break
        else:
            return
        self._match_password_to_name(name, password, seqlen)

    def _match_password_to_name(self, name, password, seqlen):
        """Check whether password 'matches' (in a sense) name."""

        def make_match(name_chunks, pwd_chunks):
            # For each subsequent name part, check if that name part starts
            # with a the leftover password. In case there is a match, shorten
            # leftover password (that's what pwd_index is for).

            # How many overlapping characters we have found so far.
            matching_length = 0
            for name in name_chunks:
                for pwd in pwd_chunks:
                    if name.startswith(pwd):
                        matching_length += len(pwd)

            return matching_length
        # Now, we have a name, 'Schnappi von Krokodil'. What password
        # variations are compared against such a name? We want to trap
        # variations like S*Krokodil, Sv-Krokodil, Schnappi-Krok and the like;
        # i.e. we want to force people NOT to use some trivial version of
        # their name.
        name = unicode(name.lower(), 'latin-1')
        password = password.lower()
        name_chunks = [x for x in name.split() if len(x) > 0]
        pwd_chunks = [x for x in re.split(r"[^a-z]+", password) if len(x) > 0]
        pwd_l33t_chunks = [x for x in re.split(
            r"[^a-z]+",
            password.translate(unicode(common.l33t_speak, 'ISO-8859-1')))
            if len(x) > 0]

        # Now, matching_length counts the number of password alpha characters
        # that overlap with the name. Let's say that if more than half the
        # password is, in fact, a match => the password is a copy of the name.
        if (make_match(name_chunks, pwd_chunks) >= seqlen or
                make_match(name_chunks, pwd_l33t_chunks) >= seqlen):
            raise common.PasswordNotGoodEnough(
                "Password cannot contain your name.")

        # Join all possible sequences of length
        def all_chunks(x):
            tmp = u''.join(x)
            if len(tmp) > seqlen:
                for i in range(len(tmp) - seqlen):
                    yield tmp[i:i+seqlen]
            else:
                yield tmp

        all_pw_chunks = set(all_chunks(password.split()))
        for name in all_chunks(name_chunks):
            if name in all_pw_chunks:
                raise common.PasswordNotGoodEnough(
                    "Password cannot contain %d characters from your name" %
                    seqlen)


class CheckSimpleMixin(CheckInvalidCharsMixin,
                       CheckLengthMixin,
                       CheckConcatMixin,
                       CheckEntropyMixin,
                       CheckCharSeqMixin,
                       CheckRepeatedPatternMixin,
                       CheckUsernameMixin,
                       CheckOwnerNameMixin):
    """ Convenience class with all mixins. """
    pass


def tests():
    pass

if __name__ == '__main__':
    del cereconf
    del cerebrum_path
    tests()