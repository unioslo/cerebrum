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


# Style specific exceptions
class RigidPasswordNotGoodEnough(PasswordNotGoodEnough):
    """Exception raised for insufficiently strong passwords."""
    pass


class PhrasePasswordNotGoodEnough(PasswordNotGoodEnough):
    """Exception raised for insufficiently strong passwords."""
    pass


# Translate strings from 'leet speak'. The value is a translation table
# bytestring for `string.translate'
l33t_speak = string.maketrans('4831!05$72', 'abeiiosstz')

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
    # Inspect the PASSWORD_CHECKS structure and decide
    # on supported password styles
    allowed_style = 'rigid'
    if (
            cereconf.PASSWORD_CHECKS.get('rigid') and
            cereconf.PASSWORD_CHECKS.get('phrase')):
        allowed_style = 'mixed'
    elif cereconf.PASSWORD_CHECKS.get('phrase'):
        allowed_style = 'phrase'
    pwstyle = allowed_style
    if pwstyle == 'mixed':
        # mark as 'phrase' if the password contains space, 'rigid' otherwise
        pwstyle = 'rigid'
        if ' ' in password:  # the same as uio.Account.is_passphrase
            pwstyle = 'phrase'

    def tree():
        return collections.defaultdict(lambda: collections.defaultdict(dict))

    # define custom exception for each password class
    exception_classes = {'rigid': RigidPasswordNotGoodEnough,
                         'phrase': PhrasePasswordNotGoodEnough}
    errors = tree()
    requirements = tree()

    for style, checks in cereconf.PASSWORD_CHECKS.items():
        for check_name, check_args in checks:
            if check_name not in _checkers:
                print('Invalid password check', repr(check_name))

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
                    ex_class = exception_classes.get(style,
                                                     PasswordNotGoodEnough)
                    # only the first error message it sent when exceptions
                    # are raised
                    err_msg = err[0]
                    if isinstance(err_msg, str):
                        # convert to unicode first in order to achieve
                        # uniform input
                        try:
                            err_msg = err_msg.decode('utf-8')
                        except UnicodeDecodeError:
                            # can occur as a result of some weird clint input
                            # just to be safe...
                            err_msg = err_msg.decode('latin-1',
                                                     errors='replace')
                    # err. messages are always UTF-8 for
                    # RigidPasswordNotGoodEnough and
                    # PhrasePasswordNotGoodEnough
                    raise ex_class(err_msg.encode('utf-8'))
                if err:
                    errors[(style, check_name)][language] = err
                else:
                    errors[(style, check_name)] = None
                requirements[(style, check_name)][language] = check.requirement

    if not structured:
        return True

    checks_structure = collections.defaultdict(list)
    total_passed = collections.defaultdict(lambda: True)
    for style, checks in cereconf.PASSWORD_CHECKS.items():
        # we want to preserve the cereconf checks order in checks_structure
        for check in checks:
            name = check[0]
            error = errors[(style, name)]
            if error:
                total_passed[style] = False
            checks_structure[style].append({name: {
                'passed': not error,
                'requirement': requirements[(style, name)],
                'errors': error,
            }})
    data = {
        'passed': total_passed[pwstyle],
        'allowed_style': allowed_style,
        'style': pwstyle,
        'checks': checks_structure,
    }
    # import json
    # print json.dumps(data, indent=4)
    return data


def pwchecker(name):
    def fn(cls):
        _checkers[name] = cls
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
                     CheckASCIICharacters,
                     CheckLatinCharacters,
                     CheckIllegalCharacters,
                     CheckSimpleCharacterGroups,
                     CheckLengthMixin,
                     CheckMultipleCharacterSets,
                     CheckCharacterSequence,
                     CheckRepeatedPattern,
                     CheckUsername,
                     CheckOwnerNameMixin,
                     CheckLettersSpacesOnly,
                     CheckNumberOfDigits,
                     CheckNumberOfLetters,
                     CheckMixedCasing)
from .dictionary import CheckPasswordDictionary
from .history_checks import CheckPasswordHistory
from .phrase import (CheckPhraseWords,
                     CheckPhraseAverageWordLength)
