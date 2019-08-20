#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Tests for Cerebrum.modules.pwcheck.history.
"""
from nose.tools import raises
from nose.plugins.skip import SkipTest

import cereconf
import os.path

from Cerebrum.modules.pwcheck.dictionary import PasswordDictionaryMixin
from Cerebrum.modules.pwcheck.common import PasswordChecker
from Cerebrum.modules.pwcheck.common import PasswordNotGoodEnough
from Cerebrum.Utils import Factory


class DictionaryCheck(PasswordDictionaryMixin, PasswordChecker):
    pass


db = Factory.get('Database')()
dictionary = DictionaryCheck(db)
expect_success = dictionary.password_good_enough
expect_failure = raises(PasswordNotGoodEnough)(dictionary.password_good_enough)


def setup_module():
    if not dictionary.password_dictionaries:
        raise SkipTest("No password dictionaries set up")
    for d in dictionary.password_dictionaries:
        if not os.path.isfile(d):
            raise SkipTest("Missing dictionary file %r" % d)


def test_non_words():
    for passwd in ('x2-W',
                   'zcyX', ):
        yield expect_success, passwd


def test_words():
    for passwd in ('hello',
                   'butter', ):
        yield expect_failure, passwd

# TODO: More tests
# TODO: Provide cereconf.PASSWD_DICT + dictionary files in test?
