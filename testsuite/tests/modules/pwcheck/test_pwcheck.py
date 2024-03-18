#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Checks for passwords and passphrases."""

from __future__ import unicode_literals

import gettext
import os

import pytest
import six

from Cerebrum.modules.pwcheck import checker
from Cerebrum.modules.pwcheck.checker import (
    PasswordNotGoodEnough,
    PhrasePasswordNotGoodEnough,
    RigidPasswordNotGoodEnough,
)


@pytest.fixture(autouse=True)
def skip_if_no_locales(cereconf):
    domain = checker.gettext_domain
    localedir = checker.locale_dir
    languages = ["no", "en"]

    # TODO: Fix Cerebrum.modules.pwcheck.checker
    # so that we can compile up the translation files in a fixture?
    if not os.path.exists(localedir):
        pytest.skip("GETTEXT_LOCALEDIR={!r} doesn't exist".format(localedir))

    try:
        gettext.translation(
            domain,
            localedir=localedir,
            languages=languages,
        ).install()
    except IOError as e:
        pytest.skip(
            "localedir={!r}, domain={!r}, languages={!r} missing: {}".format(
                localedir, domain, languages, e))
    return cereconf


@pytest.fixture
def cereconf_rigid(cereconf):
    cereconf.PASSWORD_CHECKS = {
        'rigid': (
            ('length', {'min_length': 10}),
            ('ascii_characters_only', {}),
            ('space_or_null', {}),
            ('simple_character_groups', {'min_groups': 3}),
            ('repeated_pattern', {}),
            ('character_sequence', {'char_seq_length': 3}),
        ),
    }
    return cereconf


@pytest.fixture(params=[
    'mEh19',  # 'length'
    'f0oæL!øåbarmorebarsandfoos',  # 'ascii_characters_only'
    'fO!o\0ba12rmorebarsandfoos',  # 'space_or_null'
    'nIcegOllyPazzWd',  # 'simple_character_groups'
    '2aB!2aB!2aB!2aB!',  # 'character_sequence'
])
def bad_rigid_password_strings(request):
    return request.param


def test_all_default_rigid_checks(cereconf_rigid, bad_rigid_password_strings):
    with pytest.raises(RigidPasswordNotGoodEnough):
        checker.check_password(bad_rigid_password_strings)


@pytest.fixture
def cereconf_phrase(cereconf):
    cereconf.PASSWORD_CHECKS = {
        'phrase': (
            ('length', {'min_length': 12, 'max_length': None}),
            ('num_words', {'min_words': 4, 'min_word_length': 2}),
            ('avg_word_length', {'avg_length': 4})
        ),
    }
    return cereconf


@pytest.fixture(params=[
    'mEh19 alak',  # 'length'
    'rsandfoos Opauiam Minala',  # 'num_words'
    'qwert po vert m',  # 'avg_word_length'
])
def bad_phrase_password_strings(request):
    return request.param


def test_all_default_phrase_checks(cereconf_phrase,
                                   bad_phrase_password_strings):
    with pytest.raises(PhrasePasswordNotGoodEnough):
        checker.check_password(bad_phrase_password_strings)


def test_exception_unicode():
    message = six.text_type("æøå")
    exc = PasswordNotGoodEnough(message)
    assert six.text_type(exc) == message
    assert str(exc) == message.encode("utf-8")
