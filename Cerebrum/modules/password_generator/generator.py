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

from Cerebrum import Errors
from Cerebrum.utils import text_compat
from .config import load_config

logger = logging.getLogger(__name__)


def read_dictionary_words(filename):
    """ Read words from file. """
    logger.debug("reading dictonary words from %s", repr(filename))
    with io.open(filename, encoding="utf-8") as f:
        for line in f:
            for word in line.split():
                if word:
                    yield word


class PasswordGenerator(object):
    """
    Password-generator class
    """

    def __init__(self, config=None, *args, **kw):
        """
        Constructs a PasswordGenerator.

        :param str config:
            Optional path to a valid :cls:`.config.PasswordGeneratorConfig`
            config file, or None (default) to autoload.
        """
        try:
            if config is None:
                self.config = load_config()
            else:
                self.config = load_config(filename=config)
            # Create a local random object for increased randomness
            # "Use os.urandom() or SystemRandom if you require a
            # cryptographically secure pseudo-random number generator."
            # docs.python.org/2.7/library/random.html#random.SystemRandom
            self.lrandom = random.SystemRandom()
            self.dict_words = set()
            if self.config.passphrase_dictionary:
                self.dict_words.update(read_dictionary_words(
                    self.config.passphrase_dictionary))
        except Exception as e:
            raise Errors.CerebrumError(
                "Unable to create a PasswordGenerator instance: "
                + repr(e))

    def generate_password(self):
        """
        Generates a random password
        """
        chars = text_compat.to_text(self.config.legal_characters)
        return "".join(self.lrandom.choice(chars)
                       for _ in range(self.config.password_length))

    def generate_dictionary_passphrase(self):
        """
        Generates a random dictionary based passphrase
        """
        if not self.config.passphrase_dictionary:
            raise Errors.CerebrumError('Missing passphrase-dictionary')
        if len(self.dict_words) < self.config.amount_words:
            raise Errors.CerebrumError('Passphrase-dictionary not long enough')
        return " ".join(self.lrandom.sample(self.dict_words,
                                            self.config.amount_words))
