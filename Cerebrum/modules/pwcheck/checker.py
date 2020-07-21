#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016-2017 University of Oslo, Norway
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

"""This module contains common tools for password checks."""

import cereconf

import collections
import gettext
import os
import string
import sys

import six


locale_dir = getattr(cereconf,
                     'GETTEXT_LOCALEDIR',
                     os.path.join(sys.prefix, 'share', 'locale'))
gettext_domain = getattr(cereconf, 'GETTEXT_DOMAIN', 'cerebrum')
gettext.install(gettext_domain, locale_dir, unicode=True)


class PasswordNotGoodEnough(Exception):
    """Exception raised for insufficiently strong passwords."""

    def __init__(self, message):
        # encode potential (Python 2) unicode types as byte strings
        # to ensure str(T) does not raise UnicodeEncodeError
        if six.PY2 and isinstance(message, six.text_type):
            message = message.encode("utf-8")
        super(PasswordNotGoodEnough, self).__init__(message)

    def __unicode__(self):
        # override BaseException.__unicode__() because:
        # (1) BaseException.__str__() cannot be overridden
        # (2) avoid double-decoding of unicode(T), which calls str(T)
        return str(self).decode("utf-8")


# Style specific exceptions
class RigidPasswordNotGoodEnough(PasswordNotGoodEnough):
    """Exception raised for insufficiently strong passwords."""
    pass


class PhrasePasswordNotGoodEnough(PasswordNotGoodEnough):
    """Exception raised for insufficiently strong passwords."""
    pass


l33t_speak = dict((ord(a), ord(b))
                  for a, b in zip(u'4831!05$72', u'abeiiosstz'))

_checkers = {}

_checkers_loaded = False


def load_checkers():
    global _checkers_loaded
    if not _checkers_loaded:
        from . import simple
        from . import dictionary
        from . import history_checks
        from . import phrase
        _checkers_loaded = True


def get_checkers():
    load_checkers()
    return _checkers


def check_password(password, account=None, structured=False, checkers=None):
    """
    Check password against all enabled password checks.

    :param password: the password to be validated
    :type password: str
    :param account: the account to be used or None
    :type account: Cerebrum.Account
    :param structured: send a strctured (json) output or raise an exception
    :type structured: bool
    :param checkers: (if not None) it overrides the lsit of checks defined in
                     cereconf.PASSWORD_CHECKS
    :type checkers: dict
    """
    checkers_dict = cereconf.PASSWORD_CHECKS
    if isinstance(checkers, dict):
        checkers_dict = checkers
    load_checkers()
    # Inspect the PASSWORD_CHECKS structure and decide
    # on supported password styles
    allowed_style = 'rigid'
    if checkers_dict.get('rigid') and checkers_dict.get('phrase'):
        allowed_style = 'mixed'
    elif checkers_dict.get('phrase'):
        allowed_style = 'phrase'
    pwstyle = allowed_style
    if pwstyle == 'mixed':
        # mark as 'phrase' if the password contains space, 'rigid' otherwise
        pwstyle = 'rigid'
        if password and ' ' in password:
            # the same as uio.Account.is_passphrase
            pwstyle = 'phrase'

    def tree():
        return collections.defaultdict(lambda: collections.defaultdict(dict))

    # define custom exception for each password class
    exception_classes = {'rigid': RigidPasswordNotGoodEnough,
                         'phrase': PhrasePasswordNotGoodEnough}
    errors = tree()
    requirements = tree()

    fallback_lang = "en"
    for style, checks in checkers_dict.items():
        for check_name, check_args in checks:
            for lang in getattr(cereconf, 'GETTEXT_LANGUAGE_IDS', (fallback_lang,)):
                # load the language
                gettext.translation(gettext_domain,
                                    localedir=locale_dir,
                                    languages=[lang, fallback_lang]).install()
                # instantiate password checker
                check = _checkers[check_name](**check_args)
                err = check.check_password(password, account=account)
                # bail fast if we're not returning a structure
                if not structured and err and pwstyle == style:
                    cls = exception_classes.get(style, PasswordNotGoodEnough)
                    # use only the first message we received when raising exceptions
                    raise cls(err[0])
                if err:
                    errors[(style, check_name)][lang] = err
                else:
                    errors[(style, check_name)] = None
                requirements[(style, check_name)][lang] = check.requirement

    if not structured:
        return True

    checks_structure = collections.defaultdict(list)
    total_passed = collections.defaultdict(lambda: True)
    for style, checks in checkers_dict.items():
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
    return data


def pwchecker(name):
    def fn(cls):
        _checkers[name] = cls
        return cls
    return fn


class PasswordChecker(object):
    """Base class for password checkers."""

    _requirement = ('Something')

    @property
    def requirement(self):
        return self._requirement

    def check_password(self, password):
        pass
