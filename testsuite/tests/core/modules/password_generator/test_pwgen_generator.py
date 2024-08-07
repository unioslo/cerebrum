# encoding: utf-8
"""
Tests for :mod:`Cerebrum.modules.password_generator.generator`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import io
import textwrap

import pytest

from Cerebrum.modules.password_generator import generator


#
# DefaultPasswordGenerator tests
#


def test_default_password_generator():
    gen = generator.DefaultPasswordGenerator()
    assert len(gen()) == generator.DEFAULT_PASSWORD_LENGTH


#
# PasswordGenerator tests
#

PASSWORD_LENGTH = 8
PASSWORD_CHARS = "ABCDefgh90"


@pytest.fixture
def password_gen():
    return generator.PasswordGenerator(length=PASSWORD_LENGTH,
                                       charset=PASSWORD_CHARS)


def test_password_generator_length(password_gen):
    assert len(password_gen()) == PASSWORD_LENGTH


def test_password_generator_chars(password_gen):
    assert all(c in PASSWORD_CHARS for c in password_gen())


def test_password_generator_repr(password_gen):
    assert repr(password_gen) == '<PasswordGenerator length=8 charset_size=10>'


#
# read_dictionary_words tests
#


@pytest.fixture
def dictionary(empty_file):
    with io.open(empty_file, mode="w", encoding="utf-8") as f:
        f.write(
            textwrap.dedent(
                """
                correct horse
                  battery
                staple
                """
            )
        )
    return empty_file


PASSPHRASE_DICT = [
    "correct",
    "horse",
    "battery",
    "staple",
]


def test_read_dictionary_words(dictionary):
    words = list(generator.read_dictionary_words(dictionary))
    assert words == PASSPHRASE_DICT


#
# PassphraseGenerator tests
#

PASSPHRASE_WORDS = 3


@pytest.fixture
def passphrase_gen():
    return generator.PassphraseGenerator(words=PASSPHRASE_WORDS,
                                         dictionary=PASSPHRASE_DICT)


def test_passphrase_generator_length(passphrase_gen):
    phrase = passphrase_gen()
    assert len(phrase) > 0
    assert len(phrase.split()) == PASSPHRASE_WORDS


def test_passphrase_generator_words(passphrase_gen):
    phrase = passphrase_gen()
    assert all(w in PASSPHRASE_DICT for w in phrase.split())


def test_passphrase_generator_repr(passphrase_gen):
    assert repr(passphrase_gen) == '<PassphraseGenerator words=3 dict_size=4>'


def test_passphrase_generator_empty(passphrase_gen):
    gen = generator.PassphraseGenerator(words=2, dictionary=[])
    with pytest.raises(Exception):
        gen()


#
# generator loader tests
#


@pytest.fixture
def config_file(empty_json_file, dictionary):
    """ Gets a `filename` that doesn't exist, and removes it if created. """
    with io.open(empty_json_file, mode="w", encoding="utf-8") as f:
        f.write(
            textwrap.dedent(
                """
                {{
                    "amount_words": 2,
                    "password_length": 8,
                    "legal_characters": "Tr0ub4dor&3",
                    "passphrase_dictionary": "{dictionary}"
                }}
                """
            ).strip().format(dictionary=dictionary)
        )
    return empty_json_file


def test_get_password_generator(config_file):
    gen = generator.get_password_generator(config_file)
    assert gen.length == 8
    assert set(gen.charset) == set("Tr0ub4dor&3")


def test_get_passphrase_generator(config_file):
    gen = generator.get_passphrase_generator(config_file)
    assert gen.words == 2
    assert set(gen.dictionary) == set(PASSPHRASE_DICT)
