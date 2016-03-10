#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016 University of Oslo, Norway
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
""" This module contains common tools for password checks. """

import cereconf

import collections
import gettext
import os
import string
import sys


locale_dir = getattr(cereconf,
                     'GETTEXT_LOCALEDIR',
                     os.path.join(sys.prefix, 'share', 'locale'))
gettext_domain = getattr(cereconf, 'GETTEXT_DOMAIN', 'cerebrum')
gettext.install(gettext_domain, locale_dir, unicode=1)


class PasswordNotGoodEnough(Exception):
    """Exception raised for insufficiently strong passwords."""
    pass


l33t_speak = string.maketrans('4831!05$72', 'abeiiosstz')
""" Translate strings from 'leet speak'. The value is a translation table
bytestring for `string.translate' """


# TODO: Remove me!
cereconf.PASSWORD_CHECKS = {
    'rigid': (
        ('space_or_null', {}),
        ('8bit_characters', {}),
        ('length', {'min_length': 8}),
        ('multiple_character_sets', {}),
        ('character_sequence', {'char_seq_length': 3}),
        ('repeated_pattern', {}),
        ('username', {}),
        ('owner_name', {'name_seq_len': 5}),
        ('history', {}),
        ('dictionary', {}),

    ),
    'phrase': (
        ('phrase_length', {}),
        ('phrase_num_words', {}),
        ('phrase_avg_word_length', {}),
    )
}


_checkers = {}


def check_password(password, account=None, structured=False):
    """
    Check password against all enabled password checks.

    :param password: the password to be validated
    :type password: str
    :param account: the account to be used or None
    :type account: Cerebrum.Account
    :param structured: send a strctured (json) output or raise an exception
    :type structured: bool
    """

    pwstyle = cereconf.PASSWORD_STYLE
    if pwstyle == 'mixed':
        assert account and hasattr(account, 'is_passphrase')
        pwstyle = 'phrase' if account.is_passphrase(password) else 'rigid'

    def tree():
        return collections.defaultdict(lambda: collections.defaultdict(dict))
    errors = tree()
    requirements = tree()

    for style, checks in cereconf.PASSWORD_CHECKS.items():
        for check_name, check_args in checks:
            if check_name not in _checkers:
                print 'Invalid password check', repr(check_name)

            for language in getattr(
                    cereconf, 'GETTEXT_LANGUAGE_IDS', ('en',)):
                # load the language
                gettext.translation(gettext_domain,
                                    localedir=locale_dir,
                                    languages=[language, 'en']).install()
                # instantiate password checker
                check = _checkers[check_name](**check_args)
                err = check.check_password(password, account=account)
                # bail fast if we're not returning a structure
                if not structured and err and pwstyle == style:
                    raise PasswordNotGoodEnough(err[0])
                if err:
                    errors[(style, check_name)][language] = err
                else:
                    errors[(style, check_name)] = None
                requirements[(style, check_name)][language] = check.requirement

    if not structured:
        return True

    checks = tree()
    for check, error in errors.items():
        style, name = check
        checks[style][name] = {
            'passed': not error,
            'requirement': requirements[check],
            'errors': error,
        }

    data = {
        'passed': all([x['passed'] for x in checks[pwstyle].values()]),
        'style': pwstyle,
        'checks': checks,
    }
    # import json
    # print json.dumps(data, indent=4)
    return data


def pwchecker(name):
    import inspect

    def fn(cls):
        module = inspect.getmodule(cls)
        if module is None:
            module = '__main__'
        else:
            module = module.__name__
        # if name in _enabled:
        #     _checkers[name] = cls
        #     print 'Registered checker', name, '=', cls
        # else:
        #     print 'Checker', name, 'is not enabled'
        _checkers[name] = cls
        # print 'Registered', name, '=', cls
        return cls
    return fn


class PasswordChecker(object):
    """Base class for password checkers."""

    _requirement = _('Something')

    @property
    def requirement(self):
        return self._requirement

    def check_password(self, password):
        pass

from .simple import (CheckSpaceOrNull,
                     CheckEightBitChars,
                     CheckLengthMixin,
                     CheckMultipleCharacterSets,
                     CheckCharacterSequence,
                     CheckRepeatedPattern,
                     CheckUsername,
                     CheckOwnerNameMixin)
from .dictionary import CheckPasswordDictionary
from .history import CheckPasswordHistory
from .phrase import (CheckPhraseLength,
                     CheckPhraseWords,
                     CheckPhraseAverageWordLength)
