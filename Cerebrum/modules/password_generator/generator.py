# -*- coding: utf-8 -*-
#
# Copyright 2016-2024 University of Oslo, Norway
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
"""
A dedicated module for password and passphrase generation
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging
import io
import random

import Cerebrum.Errors
from Cerebrum.utils import reprutils
from .config import load_config

logger = logging.getLogger(__name__)


DEFAULT_PASSWORD_LENGTH = 19
DEFAULT_PASSWORD_CHARSET = (
    "ABCDEFGHIJKLMNPQRSTUVWXYZ"
    "abcdefghijkmnopqrstuvwxyz"
    "23456789"
    "!#$%&()*+,-.:;<=>?@[]^_{|}~"
)


class DefaultPasswordGenerator(object):

    def __init__(self, **kwargs):
        self._random = random.SystemRandom()

    def __call__(self):
        return "".join(self._random.choice(DEFAULT_PASSWORD_CHARSET)
                       for _ in range(DEFAULT_PASSWORD_LENGTH))


class PasswordGenerator(reprutils.ReprFieldMixin, DefaultPasswordGenerator):
    """ Generate simple passwords with random characters. """

    repr_module = False
    repr_id = False
    repr_fields = ('length', 'charset_size')

    def __init__(self,
                 length=DEFAULT_PASSWORD_LENGTH,
                 charset=DEFAULT_PASSWORD_CHARSET,
                 **kwargs):
        self.length = int(length)
        self.charset = list(set(charset))
        super(PasswordGenerator, self).__init__(**kwargs)

    @property
    def charset_size(self):
        return len(self.charset)

    def __call__(self):
        return "".join(self._random.choice(self.charset)
                       for _ in range(self.length))


def read_dictionary_words(filename):
    """ Read words from file. """
    logger.debug("reading dictonary words from %s", repr(filename))
    with io.open(filename, encoding="utf-8") as f:
        for line in f:
            for word in line.split():
                if word:
                    yield word


class PassphraseGenerator(reprutils.ReprFieldMixin, DefaultPasswordGenerator):
    """
    Generate password phrases with random words from a set of words.
    """
    # Note that this class is not currently in use

    repr_module = False
    repr_id = False
    repr_fields = ('words', 'dict_size')

    def __init__(self, words, dictionary, **kwargs):
        self.words = int(words)
        self.dictionary = list(set(dictionary))
        super(PassphraseGenerator, self).__init__(**kwargs)

    @property
    def dict_size(self):
        return len(self.dictionary)

    def __call__(self):
        if len(self.dictionary) < self.words:
            raise Cerebrum.Errors.CerebrumError(
                "Passphrase dictionary not long enough")
        return " ".join(self._random.sample(self.dictionary, self.words))


def get_password_generator(config=None):
    """
    Helper to replace the legacy PasswordGenerator init.

    The old PasswordGenerator combined both password and passphrase generators,
    and auto-loaded everything from config.  This helper keeps that
    functionality, until (if) we decide to rewrite the config and loading.
    """
    try:
        if config is None:
            config = load_config()
        else:
            config = load_config(filename=config)

        return PasswordGenerator(
            length=config.password_length,
            charset=config.legal_characters,
        )

    except Exception as e:
        raise Cerebrum.Errors.CerebrumError(
            "Unable to create a PasswordGenerator instance: "
            + repr(e))


def get_passphrase_generator(config=None):
    """
    Helper to replace the legacy PasswordGenerator init.

    The old PasswordGenerator combined both password and passphrase generators,
    and auto-loaded everything from config.  This helper keeps that
    functionality, until (if) we decide to rewrite the config and loading.
    """
    try:
        if config is None:
            config = load_config()
        else:
            config = load_config(filename=config)

        return PassphraseGenerator(
            words=config.amount_words,
            dictionary=read_dictionary_words(
                config.passphrase_dictionary),
        )

    except Exception as e:
        raise Cerebrum.Errors.CerebrumError(
            "Unable to create a PassphraseGenerator instance: "
            + repr(e))
