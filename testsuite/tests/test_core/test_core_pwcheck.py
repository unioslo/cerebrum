#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Core password checks for passwords and passphrases
"""
from __future__ import unicode_literals

import cereconf

import pytest

from Cerebrum.modules.pwcheck.checker import (check_password,
                                              PasswordNotGoodEnough,
                                              RigidPasswordNotGoodEnough,
                                              PhrasePasswordNotGoodEnough)

@pytest.fixture(params=[
    'mEh19',  # 'length'
    'f0oæL!øåbarmorebarsandfoos',  # 'ascii_characters_only'
    'fO!o\0ba12rmorebarsandfoos',  # 'space_or_null'
    'nIcegOllyPazzWd',  # 'simple_character_groups'
    '2aB!2aB!2aB!2aB!',  # 'character_sequence'
])
def bad_rigid_password_strings(request):
    """
    """
    return request.param


@pytest.fixture(params=[
    'mEh19 alak',  # 'length'
    'rsandfoos Opauiam Minala',  # 'num_words'
    'qwert po vert m',  # 'avg_word_length'
])
def bad_phrase_password_strings(request):
    """
    """
    return request.param


def test_all_default_rigid_checks(bad_rigid_password_strings):
    """
    """
    cereconf.PASSWORD_CHECKS = {
        'rigid': (
            ('length', {'min_length': 10}),
            ('ascii_characters_only', {}),
            ('space_or_null', {}),
            ('simple_character_groups', {'min_groups': 3}),
            ('repeated_pattern', {}),
            ('character_sequence', {'char_seq_length': 3}),
        )}
    with pytest.raises(RigidPasswordNotGoodEnough):
        check_password.cereconf = cereconf  # ugly hack
        check_password(bad_rigid_password_strings)


def test_all_default_phrase_checks(bad_phrase_password_strings):
    """
    """
    cereconf.PASSWORD_CHECKS = {
        'phrase': (
            ('length', {'min_length': 12, 'max_length': None}),
            ('num_words', {'min_words': 4, 'min_word_length': 2}),
            ('avg_word_length', {'avg_length': 4})
        )}
    with pytest.raises(PhrasePasswordNotGoodEnough):
        check_password.cereconf = cereconf
        check_password(bad_phrase_password_strings)
