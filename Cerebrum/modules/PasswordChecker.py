# -*- coding: iso-8859-1 -*-

# Copyright 2003 University of Oslo, Norway
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

import re
import cereconf
import md5
import base64
import string
import os

from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Utils import Factory
from Cerebrum.modules import PasswordHistory

msgs = {
    'not_null_char': 
    """Please don't use the null character in your password.""",
    'atleast8':
    """The password must be at least 8 characters long.""",
    'atmost15':
"""Passwords longer than 15 characters is not compatible with all
software""",
    '8bit':
"""Don't use 8-bit characters in your password (like æøå), it creates
problems when using some keyboards.""",
    'space':
"""Don't use a space in the password.  It creates problems for the
POP3-protocol (Eudora and other e-mail readers).""",
    'mix_needed8':
"""A valid password must contain characters from at least three of
these four character groups: Uppercase letters, lowercase letters,
numbers and special characters.  If the password only contains one
uppercase letter, this must not be at the start of the password.  If
the first 8 characters only contains one number or special character,
this must not be in position 8.""",
    'mix_needed':
"""A valid password must contain characters from at least three of
these four character groups: Uppercase letters, lowercase letters,
numbers and special characters.""",
    'was_like_old':
"""That was to close to an old password.  You must select a new
one.""",
    'dict_hit': "Don't use words in a dictionary.",
    'combo': "You should not combine two words like %s and %s",
    'sequence_alphabet':
    "Don't use charactersin alpabetical or numerical order",
    'sequence_keys': "Don't use neighbouring keyboard keys",
    'repetitive_sequence':
"""Don't use repeating sequences of the same characters""",
    'uname_backwards': "Don't use your username backwards"}

class PasswordGoodEnoughException(Exception):
    """Exception raised for insufficiently strong passwds."""
    pass

class PasswordChecker(DatabaseAccessor):
    """Password checking routines.  For dictionary lookup to work, it
    is important that the dictionary files are sorted in dictionary
    order with case folded (LC_LANG=C sort -df)."""

    def look(self, FH, key, dict, fold):
        """Quick port of look.pl (distributed with perl)"""
        # TODO: Speedup could be gained for by remembering where in
        # the file we ended up last time
        blksize = os.statvfs(FH.name)[0]
        if blksize < 1 or blksize > 65536: blksize = 8192
        if dict: key = re.sub(r'[^\w\s]', '', key)
        if fold: key = key.lower()
        max = int(os.path.getsize(FH.name) / blksize)
        min = 0
        # "binary search" for a file position somewhere before our word
        while (max - min > 1):
            mid = int((max + min) / 2)
            FH.seek(mid * blksize, 0)
            if mid: line = FH.readline()  # probably a partial line
            line = FH.readline()
            line.strip()
            if dict: line = re.sub(r'[^\w\s]', '', line)
            if fold: line = line.lower()
            if line < key:
                min = mid
            else:
                max = mid
        min = min * blksize
        FH.seek(min, 0)
        if min: FH.readline()
        while 1:
            line = FH.readline()
            if len(line) == 0:
                break
            line = line.strip()
            if dict: line = re.sub(r'[^\w\s]', '', line)
            if fold: line = line.lower()
            if line >= key:
                break
            min = FH.tell()
        FH.seek(min, 0)
        return min

    def what_range(self, ch):
        """Return a range of characters depending on what the original
        character was.  This allows us to detect that the user changes
        password from '1secret' to '2secret'"""
        if not ch.isalpha():
            return range(ord(ch)-5, ord(ch)+6)
        if ch.isupper():
            return range(max(ord('A'), ord(ch)-5), min(ord('Z')+1, ord(ch)+6))
        return range(max(ord('a'), ord(ch)-5), min(ord('z')+1, ord(ch)+6))

    # TODO: Checking of password history should be optional
    def check_password_history(self, account, passwd):
        """Check wether uname had this passwd earlier.  Raises a
        PasswordGoodEnoughException if this is true"""

        pwdhist = PasswordHistory.PasswordHistory(self._db)
        variants = []
        for m in (-1, 0):
            for r in self.what_range(passwd[m]):
                if m < 0:
                    tmp = passwd[:m]+chr(r)
                else:
                    tmp = chr(r)+passwd[m+1:]
                tmp = pwdhist.encode_for_history(account, tmp)
                variants.append(tmp)
        for r in pwdhist.get_history(account.entity_id):
            if r['md5base64'] in variants:
                raise PasswordGoodEnoughException(msgs['was_like_old'])
        return 1

    def _is_word_in_dict(self, words, dict_order=1, case_fold=1):
        """Check if one of the given words are in the dictionary.  If
        one word starts with 4, and another with A, the search will
        take a loong time.  Call the routine multiple tipes to handle
        such cases."""
        words.sort()
        # We'll iterate over several dictionaries.
        for fname in cereconf.PASSWORD_DICTIONARIES:
            f = file(fname)
            self.look(f, words[0], dict_order, case_fold)
            while (1):
                line = f.readline()
                if len(line) == 0:
                    return 0
                line = line.rstrip()
                if case_fold:
                    line = line.lower()
                if dict_order:
                    line = re.sub(r'[^\w\s]', '', line)
                if line in words:
                    return 1
                if line > words[-1]:
                    return 0
        return 0

    def _check_two_word_combination(self, passwd):
        # TODO: This routine is as good as the perl version, but it
        # could be smarter by detecting more types of two-word
        # combination

        # Now check for two word-combinations.  This gets hairy.
        # We look up everything that starts with the same first
        # two letters as the password, and if the word matches the
        # head of the password, we save the rest of the password
        # in %others to be looked up later.  Passwords which have
        # a single char before or after a word are special-cased.
        
        # We take pains to disallow things like "CamelAte",
        # "CameLate" and "CamElate" but allow things like
        # "CamelatE" or "CameLAte".

        # If the password is exactly 8 characters, we also have
        # to disallow passwords that consist of a word plus the
        # BEGINNING of another word, such as "CamelFle", which
        # will warn you about "camel" and "flea".

        if re.search(r'^.[a-zA-Z]', passwd):
            others = {}
            cpasswd = passwd.lower().rstrip().replace(' ', '')
            m = re.match(r'.[a-z]*([A-Z][a-z]*)$', passwd)
            oneup = ''
            if m:
                oneup = m.group(1)
            npass = string.translate(cpasswd,
                                 string.maketrans('431!05$', 'aeiioss'))
            npass = re.sub('/[\?\!\.]$', '', npass)
            if re.search(r'.+[A-Z].*[A-Z]', passwd):
                return
            if re.search(r'^..[a-z]+$', passwd):
                others[cpasswd[1:]] = 1

            for fname in cereconf.PASSWORD_DICTIONARIES:
                two = npass[:2]
                f = file(fname)
                self.look(f, two, 1, 1)
                two = two[:-1] + chr(ord(two[-1])+1)
                while 1:
                    line = f.readline()
                    if not line:
                        break
                    line = line.rstrip().lower()
                    line = re.sub('\t.*', '', line)
                    if line > two:
                        break
                    if npass.find(line) == 0:
                        key = npass[len(line):]
                        if not re.search(r'\W', key):
                            if not (oneup and len(oneup) != len(key)):
                                others[key] = 1
            for fname in cereconf.PASSWORD_DICTIONARIES:
                f = file(fname)
                for key in others.keys():
                    self.look(f, key, 1, 1)
                    line = f.readline().rstrip()
                    line = re.sub('\t.*', '', line)
                    if (line == key or
                        (len(passwd) == 8 and re.search(r'^%s' % key, line))):
                        pre = npass[0:len(npass)-len(key)]
                        if len(pre) == 1:
                            raise PasswordGoodEnoughException(msgs['combo']
                                                               % (pre, line))
                        raise PasswordGoodEnoughException(msgs['combo']
                                                          % (pre, line))
                    elif (len(key) == 1 and
                          re.search(r'^.[a-z]+.$', npass)):
                        raise PasswordGoodEnoughException(msgs['combo']
                                                          (line, key))

    def _check_dict(self, passwd):
        """Check if the password, or simple variants of it is in the
        dictionary"""
        # TBD: should we skip any leading non-letters?
        if re.search(r'^[a-zA-Z]', passwd):
            passwd = passwd.lower()
            # Truncate common suffixes before searching dict.

            passwd = re.sub(r'\d+$', '', passwd)
            passwd = re.sub(r'\(', '', passwd)

            check_for = []
            if passwd[-2:] in ('ed', 'er'):                
                check_for.append(passwd[:-2]+"e")
            elif passwd[-3:] == 'ing':
                check_for.append(passwd[:-3]+"e")
            passwd = re.sub('s$', '', passwd)
            passwd = re.sub('ed$', '', passwd)
            passwd = re.sub('er$', '', passwd)
            passwd = re.sub('ly$', '', passwd)
            passwd = re.sub('ing$', '', passwd)
            check_for.append(passwd)
            if self._is_word_in_dict(check_for):
                raise PasswordGoodEnoughException(msgs['dict_hit'])
            nshort = string.translate(passwd,
                                      string.maketrans('431!05$', 'aeiioss'))
            if self._is_word_in_dict([nshort]):
                raise PasswordGoodEnoughException(msgs['dict_hit'])

    def _check_variation(self, passwd):
        # I'm not sure that the below is very smart.  If this rule
        # causes most users to include a digit in their password, one
        # has managed to reduce the password space by 26*2/10 provided
        # that a hacker performs a bruteforce attack

        good_try = variation = 0
        if re.search(r'[a-z]', passwd): variation += 1
        if re.search(r'[A-Z][^A-Z]{7}', passwd): good_try += 1
        if re.search(r'[A-Z]', passwd[1:8]): variation += 1
        if re.search(r'[^0-9]{7}[0-9]', passwd): good_try += 1
        if re.search(r'[0-9]', passwd[0:7]): variation += 1
        if re.search(r'[A-Za-z0-9]{7}[^A-Za-z0-9]', passwd): good_try += 1
        if re.search(r'[^A-Za-z0-9]', passwd[0:7]): variation += 1

        if variation < 3:
            if good_try:
                raise PasswordGoodEnoughException(msgs['mix_needed8'])
            else:
                raise PasswordGoodEnoughException(msgs['mix_needed'])

    def _check_sequence(self, passwd):
        passwd = passwd.lower()
        # A sequence of closely related ASCII characters?
        ok = 0
        for i in range(len(passwd)-1):
            if abs(ord(passwd[i]) - ord(passwd[i+1])):
                ok = 1
        if not ok:
            raise PasswordGoodEnoughException(msgs['sequence_alphabet'])

        # A sequence of keyboard keys?
        # TODO: 'kbd' should match a typical keyboard
        kbd = ("qwertyuiop[]asdfghjkl;'zxcvbnm,./",
               "abcdefghijklabcdefghijkabcdefghij",
               "!@#$%^&*()_+|~",
               "abcdefghijklmn",
               "-1234567890=\`",
               "kabcdefghijlmn")
        tmp = passwd
        i = 0
        while i < len(kbd):
            tmp = string.translate(tmp, string.maketrans(kbd[i], kbd[i+1]))
            i += 2
        ok = 0
        for i in range(len(tmp)-1):
            if abs(ord(tmp[i]) - ord(tmp[i+1])):
                ok = 1
        if not ok:
            raise PasswordGoodEnoughException(msgs['sequence_keys'])

    def goodenough(self, account, fullpasswd, uname=None):
        """Perform a number of checks on a password to see if it is
        random enough.  This is done by checking the mix of
        upper/lowercase letters and special characers, as well as
        checking a database.

        To use on non-existing accounts, set account=None and set uname
        to the username"""

        passwd = fullpasswd[0:8]

        if re.search(r'\0', passwd):
            raise PasswordGoodEnoughException(msgs['not_null_char'])
        if len(passwd) < 8:
            raise PasswordGoodEnoughException(msgs['atleast8'])
        if len(passwd) > 15:
            raise PasswordGoodEnoughException(msgs['atmost15'])
        if re.search(r'[\200-\376]', passwd):
            raise PasswordGoodEnoughException(msgs['8bit'])
        if re.search(r' ', passwd):
            raise PasswordGoodEnoughException(msgs['space'])

        self._check_variation(passwd)
        if account is not None:
            self.check_password_history(account, passwd)   # Will raise on error
            self.check_password_history(account, fullpasswd)
        self._check_dict(passwd)
        self._check_two_word_combination(passwd)

        for tmp in ('ibm', 'dec', 'sun', 'at&t', 'nasa', 'jan', 'feb',
                    'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep',
                    'oct', 'nov', 'dec'):
            if passwd.lower().find(tmp) != -1:
                raise PasswordGoodEnoughException(msgs['dict_hit'])

        self._check_sequence(passwd)

        # Repeated patterns: ababab, abcabc, abcdabcd
        if (re.search(r'^(..)\1\1', passwd) or
            re.search(r'^(...)\1', passwd) or
            re.search(r'^(....)\1', passwd)):
            raise PasswordGoodEnoughException(msgs['repetitive_sequence'])

        # Reversed patterns: abccba abcddcba
        if (re.search(r'^(.)(.)(.)\3\2\1', passwd) or
            re.search(r'^(.)(.)(.)(.)\4\3\2\1', passwd)):
            raise PasswordGoodEnoughException(msgs['repetitive_sequence'])

        # username backwards?
        if uname is None:
            uname = account.account_name
        tmp = list(uname)
        tmp.reverse()
        if passwd == "".join(tmp):
            raise PasswordGoodEnoughException(msgs['uname_backwards'])

def main():
    from Cerebrum.Account import Account
    db = Factory.get('Database')()
    pc = PasswordChecker(db)
    account = Account(db)
    account.find_by_name('bootstrap_account')
    if 0:
        print "Ret: %s" % pc._is_word_in_dict(
            ['lastata', 'lastebul', 'lastebol', 'lastebil'],
            dict_order=1, case_fold=0)
    elif 0:
        pc._check_dict("Al3ne")
    elif 0:
        pc._check_two_word_combination("CamElate")
    print "ok"

if __name__ == '__main__':
    main()
