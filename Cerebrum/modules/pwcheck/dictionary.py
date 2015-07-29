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
import string
import os

import cerebrum_path
import cereconf
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Utils import Factory
from Cerebrum.modules.pwcheck.history import PasswordHistory
from Cerebrum import Errors



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
"""For a password to be valid the first 8 characters must be from at
least three of these four character groups: Uppercase letters,
lowercase letters, numbers and special characters.  If the password
only contains one uppercase letter, this must not be at the start of
the password.  If the first 8 characters only contains one number or
special character, this must not be in position 8.""",
    'mix_needed':
"""For a password to be valid the first 8 characters must be from at
least three of these four character groups: Uppercase letters,
lowercase letters, numbers and special characters.""",
    'was_like_old':
"""That was to close to an old password.  You must select a new
one.""",
    'dict_hit': "Don't use words in a dictionary.",
    'dict_hit_joined':  "Don't use words in a dictionary or concatenations.",
    'combo': "You should not combine two words like %s and %s",
    'sequence_alphabet':
    "Don't use characters in alpabetical or numerical order",
    'sequence_keys': "Don't use neighbouring keyboard keys",
    'repetitive_sequence':
"""Don't use repeating sequences of the same characters""",
    'uname_backwards': "Don't use your username backwards",
    'uname_forwards': "Don't use your username",
    'password_is_a_name': "Don't use your name as password",
    'used_parentheses': "\nDon't enclose password in parentheses."}

class PasswordGoodEnoughException(Exception):
    """Exception raised for insufficiently strong passwds."""
    pass

class PasswordChecker(DatabaseAccessor):
    """Password checking routines.  For dictionary lookup to work, it
    is important that the dictionary files are sorted in dictionary
    order with case folded (LC_LANG=C sort -df)."""

    def __init__(self, *rest, **kw):
        super(PasswordChecker, self).__init__(*rest, **kw)
        # Make a translation table for l33t-style transliteration
        self.l33t_speak = string.maketrans('431!05$', 'aeiioss')
    # end __init__


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

        pwdhist = PasswordHistory(self._db)
        variants = []
        for m in (-1, 0):
            for r in self.what_range(passwd[m]):
                if m < 0:
                    tmp = passwd[:m]+chr(r)
                else:
                    tmp = chr(r)+passwd[m+1:]
                tmp = pwdhist.encode_for_history(account.account_name, tmp)
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
        
        words = [w for w in words if len(w) > 3]
        if len(words) == 0:
            return 0
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
                for word in words:
                    if line.startswith(word):
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
            npass = string.translate(cpasswd, self.l33t_speak)

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
                                                          % (line, key))

    def _check_dict(self, passwd):
        """Check if the password, or simple variants of it is in the
        dictionary."""

        passwd = passwd.lower()
        if re.search(r'^[a-z]', passwd):
            # Truncate common suffixes before searching dict.

            passwd = re.sub(r'\d+$', '', passwd)

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
        else:
            if self._is_word_in_dict([re.sub(r'^[^a-z]+', '', passwd)]):
                raise PasswordGoodEnoughException(msgs['dict_hit'])

        nshort = string.translate(passwd, self.l33t_speak)
        if self._is_word_in_dict([nshort]):
            raise PasswordGoodEnoughException(msgs['dict_hit'])
    # end _check_dict
    

    def _check_variation(self, passwd):
        """Check that the password is 'varied enough'.

        We want at least 3 out of these 4:

          - lowercase
          - uppercase
          - digits
          - special chars
        """
        
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

        # A sequence of closely related ASCII characters.
        ok = 0
        for i in range(len(passwd)-1):
            if abs(ord(passwd[i]) - ord(passwd[i+1])) > 1:
                ok = 1
        if not ok:
            raise PasswordGoodEnoughException(msgs['sequence_alphabet'])

        # TODO: 'kbd' should probably try a number of typical layouts.
        # Rows may be of different lengths, but the same symbol CANNOT occur
        # more than once.
        keyboard_rows = ("qwertyuiop[]",
                         "asdfghjkl;'",
                         "zxcvbnm,./", 
                         "!@#$%^&*()_+|~",
                         "-1234567890=\`")
        tmp = passwd
        last_index = 0
        #
        # The idea is to map each keyboard row into its own interval of
        # consecutive chars (we don't care they may be non-printable). The
        # code later checks that there does in fact exist at least 2
        # consecutive chars in the password that differ by more than one.
        for row in keyboard_rows:
            translation_map = ''.join(chr(x) for x in range(last_index,
                                                            last_index+len(row)))
            last_index += len(row)
            tmp = string.translate(tmp,
                                   string.maketrans(row, translation_map))
            
        # Is there at least 1 pair of consecutive chars that differ by more
        # than 1? 
        ok = 0
        for i in range(len(tmp)-1):
            if abs(ord(tmp[i]) - ord(tmp[i+1])) > 1:
                ok = 1
        if not ok:
            raise PasswordGoodEnoughException(msgs['sequence_keys'])
    # end _check_sequence


    def _check_password_has_no_invalid_characters(self, password):
        """Check that only valid characters are allowed.
        """

        # nul is not allowed
        if '\0' in password:
            raise PasswordGoodEnoughException(msgs['not_null_char'])

        if ' ' in password:
            raise PasswordGoodEnoughException(msgs['space'])

        # 8-bit chars are problematic 
        if re.search(r'[\200-\376]', password):
            raise PasswordGoodEnoughException(msgs['8bit'])

    # end _check_password_has_no_invalid_characters


    def _strip_enclosing_parenthesis(self, password):
        """Strip surrounding parentheses, to prevent people from creating
        'secure' passwords like '(house)'.
        """

        if password[0] in "([{<":
            password = password[1:]
            if password[-1] in ">}])":
                password = password[:-1]

        return password
    # end _strip_enclosing_parenthesis
    

    def _check_password_has_proper_length(self, password):
        """A password is between 8 and 15 characters.
        
        NB! To prevent people from subverting the passwords, we have to strip
        parentheses from the passwords.
        """

        if len(password) < 8:
            raise PasswordGoodEnoughException(msgs['atleast8'])

        stripped_password = self._strip_enclosing_parenthesis(password)
        if len(stripped_password) > 15:
            raise PasswordGoodEnoughException(msgs['atmost15'])
    # end _check_password_has_proper_length


    def _check_password_is_not_two_concatenated_words(self, fullpwd, pwd):
        """We disallow passwords like 'Camel*Toe'.

        (Passwords are pretty legit otherwise, except that they are
        essentially 2 dictionary words combined).

        TBD: Is this really a good idea? This check disallows passwords like
        'Hsy#Klj7', which is clearly completely insane.
        """

        # Concatenated names or words from dictionaries
        if (re.search(r'^[A-Z][a-z]+[^A-Za-z0-9][A-Z][a-z]*$', pwd[0:7]) or
            re.search(r'^[A-Z][a-z]+[^A-Za-z0-9][A-Z][a-z]*$', fullpwd)):
            raise PasswordGoodEnoughException(msgs['dict_hit_joined'])
    # end _check_password_is_not_two_concatenated_words


    def _check_illegal_words(self, password):
        """Check that certain words are NOT part of the password.

        The reasoning is that using these substrings would severely compromise
        password strength.
        """

        normalised = password.lower()
        for tmp in ('ibm', 'dec', 'sun', 'at&t', 'nasa', 'jan', 'feb',
                    'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep',
                    'oct', 'nov', 'dec'):
            if tmp in normalised:
                raise PasswordGoodEnoughException(msgs['dict_hit'])
    # end _check_illegal_words



    def _check_repeated_patterns(self, password):
        """Check that the password does not have certain regularity.
        """
        
        # Repeated patterns: ababab, abcabc, abcdabcd
        if (re.search(r'^(..)\1\1', password) or
            re.search(r'^(...)\1', password) or
            re.search(r'^(....)\1', password)):
            raise PasswordGoodEnoughException(msgs['repetitive_sequence'])

        # Reversed patterns: abccba abcddcba
        if (re.search(r'^(.)(.)(.)\3\2\1', password) or
            re.search(r'^(.)(.)(.)(.)\4\3\2\1', password)):
            raise PasswordGoodEnoughException(msgs['repetitive_sequence'])

    # end _check_repeated_patterns


    def _check_username(self, account, password, uname):
        """Check that the password does not match username.
        """

        if uname is None:
            uname = account.account_name

        # password cannot equal the username
        if password.lower() == uname:
            raise PasswordGoodEnoughException(msgs["uname_forwards"])

        # password cannot equal reversed username
        if password.lower() == uname[::-1]:
            raise PasswordGoodEnoughException(msgs['uname_backwards'])
    # end _check_username



    def _match_password_to_name(self, name, password):
        """Check whether password 'matches' (in a sense) name.
        """

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
        # end make_match
            
        # Now, we have a name, 'Schnappi von Krokodil'. What password
        # variations are compared against such a name? We want to trap
        # variations like S*Krokodil, Sv-Krokodil, Schnappi-Krok and the like;
        # i.e. we want to force people NOT to use some trivial version of
        # their name.
        name = name.lower()
        password = password.lower()
        name_chunks = [x for x in name.split() if len(x) > 0]
        pwd_chunks = [x for x in re.split(r"[^a-z]+", password) if len(x) > 0]
        pwd_l33t_chunks = [x for x in re.split(r"[^a-z]+",
                                               password.translate(self.l33t_speak))
                           if len(x) > 0]

        # Now, matching_length counts the number of password alpha characters
        # that overlap with the name. Let's say that if more than half the
        # password is, in fact, a match => the password is a copy of the name.
        if (make_match(name_chunks, pwd_chunks) > len(password)/2 or
            make_match(name_chunks, pwd_l33t_chunks) > len(password)/2):
            raise PasswordGoodEnoughException(msgs["password_is_a_name"])
    # end _match_password_to_name
    


    def _check_human_owner(self, account, password):
        """Make sure that password is not some variation of the human owner's
        name.
        """

        if account is None:
            return

        # First, do we have a human owner at all?
        person = Factory.get("Person")(self._db)
        const = Factory.get("Constants")()
        try:
            person.find(account.owner_id)
        except Errors.NotFoundError:
            # This cannot be, really? But for password purposes, it means
            # there is nothing to check.
            return

        # Which name to use? Let's grab the first full name we find
        for row in person.get_all_names():
            if row["name_variant"] == const.name_full:
                name = row["name"]
                break
        else:
            return 

        self._match_password_to_name(name, password)
    # end _check_human_owner
        


    def goodenough(self, account, fullpasswd, uname=None):
        """Perform a number of checks on a password to see if it is
        random enough.  This is done by checking the mix of
        upper/lowercase letters and special characers, as well as
        checking a database.

        To use on non-existing accounts, set account=None and set uname
        to the username"""

        passwd = fullpasswd[0:8]

        self._check_password_has_no_invalid_characters(fullpasswd)

        self._check_password_has_proper_length(passwd)

        passwd = self._strip_enclosing_parenthesis(passwd)

        self._check_password_is_not_two_concatenated_words(fullpasswd, passwd)

        self._check_variation(passwd)

        if account is not None:
            self.check_password_history(account, passwd)   # Will raise on error
            self.check_password_history(account, fullpasswd)

        self._check_dict(passwd)

        self._check_two_word_combination(passwd)

        self._check_illegal_words(passwd)

        self._check_sequence(passwd)

        self._check_repeated_patterns(passwd)

        self._check_username(account, passwd, uname)

        self._check_human_owner(account, passwd)
    # end goodenough


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



########################################################################
#
# Password tests
#
# Usage:
#
# nosetests -s -v PasswordChecker.py
# py.test -s -v PasswordChecker
#
########################################################################
def test_nul_byte_fails():
    """Nul byte is not a valid password component."""
    db = Factory.get("Database")()
    pc = PasswordChecker(db)
    try:
        pc._check_password_has_no_invalid_characters("foo\0bar")
        assert False
    except PasswordGoodEnoughException:
        pass
# end test_nul_byte_fails

# TODO: Deprecate when switching over to Python 3.x
def test_pure_latin1_fails():
    """Chars outside of ascii range may be problematic, and we disallow them.
    """

    db = Factory.get("Database")()
    pc = PasswordChecker(db)
    try:
        pc._check_password_has_no_invalid_characters("fooæøåbar")
        pc._check_password_has_no_invalid_characters("{[(<fooæøåbar")
        assert False
    except PasswordGoodEnoughException:
        pass
# end test_pure_latin1_fails


def test_pwd_stripping_without_parens():
    db = Factory.get("Database")()
    pc = PasswordChecker(db)

    pc._strip_enclosing_parenthesis("foobar") == "foobar"
# end test_pwd_stripping_without_parens


def test_pwd_stripping_with_parens():
    """Check hos parentheses stripping works"""
    
    db = Factory.get("Database")()
    pc = PasswordChecker(db)

    root = "cat"
    patterns = list()
    for lparen, rparen in ("()",
                           "[]",
                           "()",
                           "{}"):
        # just opening paren
        patterns.append((lparen + root, root))
        # just closing paren
        patterns.append((root + rparen, root))
        # both
        patterns.append((lparen + root + rparen, root))

    # mismatches parens
    patterns.append(("(" + root + ">", root))

    for original, stripped in patterns:
        pc._strip_enclosing_parenthesis(original) == stripped
# end test_pwd_stripping_with_parens


def test_pwd_stripping_does_not_strip_closing():
    """Check that paren stripping ignores right parenthesis at the start.
    """

    db = Factory.get("Database")()
    pc = PasswordChecker(db)

    root = "cat"
    patterns = list()
    for lparen, rparen in (")(",
                           "][",
                           ")(",
                           "}{"):
        # just opening paren
        patterns.append((lparen + root, lparen + root))
        # just closing paren
        patterns.append((root + rparen, root + rparen))
        # both
        patterns.append((lparen + root + rparen, lparen + root + rparen))

    # mismatches parens
    patterns.append((">" + root + "(", ">" + root + "("))

    for original, stripped in patterns:
        pc._strip_enclosing_parenthesis(original) == stripped
# end test_pwd_stripping_does_not_strip_closing
   
    

def test_short_pwd_fails1():
    db = Factory.get("Database")()
    pc = PasswordChecker(db)

    try:
        pc._check_password_has_proper_length("123")
        assert False
    except PasswordGoodEnoughException:
        pass
# end test_short_pwd_fails
        
    
def test_short_pwd_fails2():
    db = Factory.get("Database")()
    pc = PasswordChecker(db)

    try:
        pc._check_password_has_proper_length("1234567")
        assert False
    except PasswordGoodEnoughException:
        pass
# end test_short_pwd_fails


def test_password_too_long():
    db = Factory.get("Database")()
    pc = PasswordChecker(db)

    try:
        pc._check_password_has_proper_length("-"*20)
        assert False
    except PasswordGoodEnoughException:
        pass
# end test_password_too_long


def test_check_parens_do_not_reduce_pwd_length():
    """Make sure that stripping surrounding parens does NOT affect min
    password length"""

    db = Factory.get("Database")()
    pc = PasswordChecker(db)

    # This must succeed (8 chars, 1st is stripped, since it's a paren, but it
    # still counts towards *minimum* pwd length)
    pc._check_password_has_proper_length("{1234567")
# end test_check_parens_do_not_reduce_pwd_length


def test_check_parens_reduce_max_length():
    """Make sure that stripping surrounding parens does in fact affect max
    password length"""

    db = Factory.get("Database")()
    pc = PasswordChecker(db)

    # This must succeed (17 chars, but the surrounding parens are stripped
    pc._check_password_has_proper_length("{" + "-"*15 + ")")
# end test_check_parens_do_not_reduce_pwd_length
    


def test_check_two_word_concat_fails():
    """Check that a password does not look like two words with a separator in
    the middle.

    I.e. we do NOT allow 'Camel*Toe' (but this test DOES allow 'CamelToe')
    """

    db = Factory.get("Database")()
    pc = PasswordChecker(db)

    try:
        pwd = "Camel*Toe"
        pc._check_password_is_not_two_concatenated_words(pwd, pwd)
        assert False
    except PasswordGoodEnoughException:
        pass

    # this must succeed, though
    pwd = "CmToe"
    pc._check_password_is_not_two_concatenated_words(pwd, pwd)
# end test_check_two_word_concat_fails


def test_invalid_variations():
    """Test that our passwords are 'varied enough'."""

    db = Factory.get("Database")()
    pc = PasswordChecker(db)

    failing_pwds = ("House",
                    "housE",
                    "hou3se",
                    "Hous3",    # <- fails, because leadnig upcase does NOT
                                #    contribute to variation score
                    "12345678", # <- just digits
                    "house",    # <- just lowercase
                    "HOUSE",    # <- just upcase
                    "hoUSE",    # <- just up+low
                    "ho123",    # <- just low+digits
                    "ho()/)",   # <- just low+special
                    "HO123",    # <- just up+digits
                    "HO/(#)",   # <- just up+special
                    "12()&)",   # <- juts digits+special
                    )

    for fail in failing_pwds:
        try:
            pc._check_variation(fail)
            assert False, "%s should have failed" % fail
        except PasswordGoodEnoughException:
            pass
# end test_invalid_variations



def test_valid_variations():
    """Test that our passwords are 'varied enough'."""

    db = Factory.get("Database")()
    pc = PasswordChecker(db)
    successful_pwds = ("hOus3", "h()us3",)
    for success in successful_pwds:
        try:
            pc._check_variation(success)
        except:
            print "Failed", success
            raise
# end test_valid_variations


def test_invalid_sequences():
    db = Factory.get("Database")()
    pc = PasswordChecker(db)

    fail_seqs = ("0123456789",       # <- digits
                 "abcdefg",          # <- alphabet
                 "hijkl",
                 "mnopqrst",
                 "uvwxyz",
                 "qwerty", "rtyuio", # <- 'qwerty'-row
                 "asdfg", "ghjkl",   # <- 'asdf'-row
                 "zxcvb", "bnm,.",   # <- 'zxcv'-row
                 '!@#$%^',           # <- row with digits
                 )
    for fail in fail_seqs:
        try:
            pc._check_sequence(fail)
            assert False, "%s should have failed" % fail
        except PasswordGoodEnoughException:
            pass
# end test_invalid_sequences


def test_valid_sequences():
    db = Factory.get("Database")()
    pc = PasswordChecker(db)

    success_seqs = ("qwrty",         # gap of 2
                    "abcdfg",        # gap of 2
                    "123567",        # gap of 2
                    "bygg",          # used to fail
                    "yhn",           # same offset in different kbd rows
                    )
    for success in success_seqs:
        try:
            pc._check_sequence(success)
        except:
            print "Failed", success
            raise
# end test_valid_sequences


def test_repetition1():
    """Check that repeating patterns fail."""
    db = Factory.get("Database")()
    pc = PasswordChecker(db)

    fail_seqs = ("aaaaaa",
                 "ababab",
                 "bababa",
                 "abcabc",
                 "cbacba",
                 "abcdabcd",
                 "abccba",
                 "xyz11zyx",)

    for fail in fail_seqs:
        try:
            pc._check_repeated_patterns(fail)
            assert False, "%s should have failed" % fail
        except PasswordGoodEnoughException:
            pass
# end test_repetition1



def test_repetition2():
    """Some repetition should be allowed"""

    db = Factory.get("Database")()
    pc = PasswordChecker(db)
    success_seqs = ("aaaa",     # <- repetition is too short :)
                    "ababa",    # <- we need at least 3 consec pairs for a fail
                    "abcdab",   # <- non-consecutive repetition
                    "ab*ba",    # <- same story
                    "abc*cba",  # <- same story
                    "a1a2a3", 
                    )
    for success in success_seqs:
        try:
            pc._check_repeated_patterns(success)
        except:
            print "Failed", success
            raise
# end test_repetition2


def test_uname_password():
    """Test that uname != password."""

    db = Factory.get("Database")()
    pc = PasswordChecker(db)
    user = "schnappi"
    pwds = (user, user[::-1])
    for fail in pwds:
        try:
            pc._check_username(None, fail, user)
            assert False, "%s should have failed" % fail
        except PasswordGoodEnoughException:
            pass
# end test_uname_password


def test_failing_name_passwords():
    """Check that a password derived from human's name fails.
    """

    db = Factory.get("Database")()
    pc = PasswordChecker(db)

    name = "Schnappi von Krokodil"
    failures = ("Schn-Kroko",
                "S*Krokodil",
                "Sc#Krok",
                "schn4ppi",
                "Schn-vo",
                "S-v-Kroko",
                "Kroko-Sch",
                "von-Schn",
                "Schn4Schn",
                "Kroko-Kroko",
                )
    for fail in failures:
        try:
            pc._match_password_to_name(name, fail)
            assert False, "%s should have failed" % fail
        except PasswordGoodEnoughException:
            pass

    name = "Ola Nordmann"
    failures = ("O-Nordmann",
                "O-Nordman",
                "Nor-Ola",
                "Nord-Ola",
                "N-Ola",
                "No*Ola",)
    for fail in failures:
        try:
            pc._match_password_to_name(name, fail)
            assert False, "%s should have failed" % fail
        except PasswordGoodEnoughException:
            pass
# end test_failing_name_passwords


def test_allowed_name_passwords():
    """Check that sufficient difference from name is allowed for passwords.
    """

    db = Factory.get("Database")()
    pc = PasswordChecker(db)

    name = "Schnappi von Krokodil"
    successes = ("S-Kr-blab",   # <- too few chars match
                 "ScOn*Krble",  # <- not enough chars in each prefix for a match
                 )
    for success in successes:
        try:
            pc._match_password_to_name(name, success)
        except:
            print "Failed", success
            raise
# end test_allowed_name_passwords



if __name__ == '__main__':
    main()
