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

import string
import collections


class PasswordNotGoodEnough(Exception):
    """Exception raised for insufficiently strong passwords."""
    pass


l33t_speak = string.maketrans('4831!05$72', 'abeiiosstz')
""" Translate strings from 'leet speak'. The value is a translation table
bytestring for `string.translate' """


# TODO: Remove me!
cereconf.PASSWORD_CHECKS = {
    'rigid': {
        'space_or_null': {},
        '8bit_characters': {},
        'length': {'min_length': 8},
        'multiple_character_sets': {},
        'character_sequence': {'char_seq_length': 3},
        'repeated_pattern': {},
        'username': {},
        'owner_name': {'name_seq_len': 5},
        'history': {},
        'dictionary': {},

    },
    'phrase': {
    }
}


_checkers = collections.defaultdict(lambda: collections.defaultdict(dict))


def check_password(password, account=None, structured=False):
    """Check password against all enabled password checks."""

    pwstyle = cereconf.PASSWORD_STYLE
    if pwstyle == 'mixed':
        assert account and hasattr(account, 'is_passphrase')
        pwstyle = 'phrase' if account.is_passphrase(password) else 'rigid'


    errors = {}
    requirements = {}
    for name, cls in _checkers.items():
        if name not in cereconf.PASSWORD_CHECKS.get(pwstyle).keys():
            print 'Skipping', name, ', not in PASSWORD_CHECKS'
            continue
        checker_args = {}
        check = cls(**checker_args)
        err = check.check_password(password, account=account)
        if not structured and err:
            raise PasswordNotGoodEnough(err[0])
        errors[name] = err or None
        requirements[name] = check.requirement

    if not structured:
        return True

    # print 'Errors encountered'
    # for name, error in errors.items():
    #     print name, "\t", error

    # {
    #     "passed": false,
    #     "style": "phrase",
    #     "checks": {
    #         "passphrase_min_words": {
    #             "passed": true,
    #             "requirement": {
    #                 "no": "Må bestå av minst 4 ord på minst 2 bokstaver",
    #                 "en": "Must have at least 4 words of length 2"
    #             },
    #             "messages": null,
    #         },
    #         "passphrase_avg_word_len": {
    #             "passed": false,
    #             "requirement": {
    #                 "no": "Lengden på ordene må i gjennomsnitt være minst 4 tegn",
    #                 "en": "Password words must be in average at least 4 characters long"
    #             },
    #             "messages": null,
    #         },
    #     },
    # }

    passed = not any(errors.values())
    checks = {}

    for name, error in errors.items():
        # TODO: Add translations
        checks[name] = {
            'passed': not error,
            'requirement': requirements[name],
            'messages': error,
        }

    data = {
        'passed': passed,
        'style': pwstyle,
        'checks': checks,
    }

    import pprint
    pp = pprint.PrettyPrinter(indent=2)
    pp.pprint(data)

    # return data


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
        print 'Registered', name, '=', cls
        return cls
    return fn


class PasswordChecker(object):
    """Base class for password checkers."""

    _requirement = 'Something'

    @property
    def requirement(self):
        return self._requirement

    def check_password(self, password):
        pass

from .simple import *
from .dictionary import CheckPasswordDictionary
from .history import CheckPasswordHistory
