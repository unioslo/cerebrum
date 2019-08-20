#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2018 University of Oslo, Norway
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
"""This module contains a password dictionary check.

The PasswordDictionaryMixin class is used to check variations of a password
against dictionaries of words and names. This raises the bar for dictionary
attacks.

HISTORY
-------
This module was moved from Cerebrum.modules.PasswordChecker. For the old
structure of the dictionary checks, please see:

> commit 9a01d8b6ac93513a57ac8d6393de842939582f51
> Mon Jul 20 14:12:55 2015 +0200
"""
from __future__ import unicode_literals

import io
import os
import re
import string

import cereconf

from .checker import pwchecker, PasswordChecker, l33t_speak


def additional_words():
    """
    Strings that should not exist in the first 8 characters of any password.
    """
    for w in ('ibm', 'dec', 'sun', 'at&t', 'nasa', 'jan', 'feb', 'mar', 'apr',
              'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'):
        yield w


def look(FH, key, dictn, fold):
    """Quick port of look.pl (distributed with perl 4)

    http://cpansearch.perl.org/src/ZEFRAM/Perl4-CoreLibs-0.003/lib/look.pl
    """
    # TODO: Speedup could be gained for by remembering where in
    # the file we ended up last time
    blksize = os.statvfs(FH.name)[0]
    if blksize < 1 or blksize > 65536:
        blksize = 8192
    if dictn:
        key = re.sub(r'[^\w\s]', '', key)
    if fold:
        key = key.lower()
    max = int(os.path.getsize(FH.name) / blksize)
    min = 0
    # "binary search" for a file position somewhere before our word
    while (max - min > 1):
        mid = int((max + min) / 2)
        FH.seek(mid * blksize, 0)
        if mid:
            line = FH.readline()
        line = FH.readline()
        line.strip()
        if dictn:
            line = re.sub(r'[^\w\s]', '', line)
        if fold:
            line = line.lower()
        if line < key:
            min = mid
        else:
            max = mid
    min = min * blksize
    FH.seek(min, 0)
    if min:
        FH.readline()
    while 1:
        line = FH.readline()
        if len(line) == 0:
            break
        line = line.strip()
        if dictn:
            line = re.sub(r'[^\w\s]', '', line)
        if fold:
            line = line.lower()
        if line >= key:
            break
        min = FH.tell()
    FH.seek(min, 0)
    return min


def is_word_in_dicts(dictionaries,
                     words,
                     dict_order=1,
                     case_fold=1,
                     file_encoding='utf-8'):
    """Check if one of the given words are in the dictionary.

    If one word starts with 4, and another with A, the search will take a
    loong time. Call the routine multiple times to handle such cases.

    :param list dictionaries: A list of dictionary files
    :param list words: A list of similar words to try
    :param bool dict_order: ...
    :param bool case_fold: ...

    :return bool: True if any word is found in any dictionary.
    """
    words = [w for w in words if len(w) > 3]
    if len(words) == 0:
        return False
    words.sort()
    # We'll iterate over several dictionaries.
    for fname in dictionaries:
        with io.open(fname, encoding=file_encoding) as f:
            look(f, words[0], dict_order, case_fold)
            while (1):
                line = f.readline()
                if len(line) == 0:
                    return False
                line = line.rstrip()
                if case_fold:
                    line = line.lower()
                if dict_order:
                    line = re.sub(r'[^\w\s]', '', line)
                for word in words:
                    if line.startswith(word):
                        return True
                if line > words[-1]:
                    return False
    return False


def check_dict(dictionaries, baseword, file_encoding='utf-8'):
    """Check if variations of `baseword' is in the dictionary."""
    baseword = baseword.lower()
    if re.search(r'^[a-z]', baseword):
        # Truncate common suffixes before searching dict.
        baseword = re.sub(r'\d+$', '', baseword)

        check_for = []
        if baseword[-2:] in ('ed', 'er'):
            check_for.append(baseword[:-2]+"e")
        elif baseword[-3:] == 'ing':
            check_for.append(baseword[:-3]+"e")

        baseword = re.sub('s$', '', baseword)
        baseword = re.sub('ed$', '', baseword)
        baseword = re.sub('er$', '', baseword)
        baseword = re.sub('ly$', '', baseword)
        baseword = re.sub('ing$', '', baseword)

        check_for.append(baseword)

        if is_word_in_dicts(dictionaries, check_for):
            return True
    else:
        if is_word_in_dicts(dictionaries, [re.sub(r'^[^a-z]+', '', baseword)]):
            return True
    nshort = baseword.translate(l33t_speak)
    if is_word_in_dicts(dictionaries, [nshort], file_encoding=file_encoding):
        return True
    return False


def check_two_word_combinations(dictionaries, word, file_encoding='utf-8'):
    """Check for two word-combinations.

    This gets hairy. We look up everything that starts with the same first two
    letters as the password, and if the word matches the head of the password,
    we save the rest of the password in %others to be looked up later.
    Passwords which have a single char before or after a word are
    special-cased.

    We take pains to disallow things like "CamelAte", "CameLate" and
    "CamElate" but allow things like "CamelatE" or "CameLAte".

    If the password is exactly 8 characters, we also have to disallow
    passwords that consist of a word plus the BEGINNING of another word,
    such as "CamelFle", which will warn you about "camel" and "flea".

    TODO: This routine is as good as the perl version, but it could be
    smarter by detecting more types of two-word combination
    """
    if re.search(r'^.[a-zA-Z]', word):
        others = {}
        cword = word.lower().rstrip().replace(' ', '')
        m = re.match(r'.[a-z]*([A-Z][a-z]*)$', word)
        oneup = ''
        if m:
            oneup = m.group(1)
        npass = cword.translate(l33t_speak)
        npass = re.sub('/[\?\!\.]$', '', npass)
        if re.search(r'.+[A-Z].*[A-Z]', word):
            return None
        if re.search(r'^..[a-z]+$', word):
            others[cword[1:]] = 1

        for fname in dictionaries:
            two = npass[:2]
            with io.open(fname, encoding=file_encoding) as f:
                look(f, two, 1, 1)
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

        for fname in dictionaries:
            with io.open(fname, encoding=file_encoding) as f:
                for key in others.keys():
                    try:
                        look(f, key, 1, 1)
                        line = f.readline().rstrip()
                        line = re.sub('\t.*', '', line)
                        if (line == key or (len(word) == 8 and
                                            re.search(r'^%s' % key, line))):
                            pre = npass[0:len(npass)-len(key)]
                            return (pre, line)
                        elif (len(key) == 1 and
                              re.search(r'^.[a-z]+.$', npass)):
                            return (line, key)
                    except UnicodeDecodeError:
                        continue
        return None


@pwchecker('dictionary')
class CheckPasswordDictionary(PasswordChecker):
    """Check if password contains dictionary words."""

    def __init__(self, file_encoding='utf-8'):
        self._requirement = _('Must not contain dictionary words')
        self._file_encoding = file_encoding

    @property
    def password_dictionaries(self):
        """The dictionary files to check."""
        return getattr(cereconf, 'PASSWORD_DICTIONARIES', [])

    def check_password(self, password, account=None):
        """Check password against a dictionary."""
        try:
            if check_dict(self.password_dictionaries,
                          password[0:8],
                          file_encoding=self._file_encoding):
                return [_('Password cannot contain dictionary words')]

            err = check_two_word_combinations(
                self.password_dictionaries,
                password[0:8],
                file_encoding=self._file_encoding)
        except UnicodeDecodeError:
            pass
        if err and len(err) == 2:
            return [
                _('You should not combine two words like {word1} and '
                  '{word2}').format(word1=err[0], word2=err[1])]

        for tmp in additional_words():
            if tmp in password[0:8].lower():
                return [_('Password cannot contain dictionary words')]
