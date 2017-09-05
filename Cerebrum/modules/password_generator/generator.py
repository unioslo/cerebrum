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
"""
A dedicated module for password and passphrase generation
"""
import random

import cereconf

from Cerebrum import Errors

from Cerebrum.modules.password_generator.config import load_config


class PasswordGenerator(object):
    """
    Password-generator class
    """

    def __init__(self, config=None, *args, **kw):
        """ Constructs a PasswordGenerator.

        :param Cerebrum.config.configuration.Configuration config:
            The Configuration object for the password_generator module.
        """
        try:
            if config is None:
                self.config = load_config()
            else:
                self.config = load_config(filepath=config)
            # Create a local random object for increased randomness
            # "Use os.urandom() or SystemRandom if you require a
            # cryptographically secure pseudo-random number generator."
            # docs.python.org/2.7/library/random.html#random.SystemRandom
            self.lrandom = random.SystemRandom()
            self.dict_words = []
            if self.config.passphrase_dictionary:
                with open(self.config.passphrase_dictionary) as fp:
                    for line in fp:
                        try:
                            # assume UTF-8 encoded text-file
                            self.dict_words.append(
                                line.strip().decode('utf-8'))
                        except:
                            continue
        except Exception as e:
            raise Errors.CerebrumError('Unable to create a PasswordGenerator '
                                       'instance: {error}'.format(error=e))

    def generate_password(self):
        """
        Generates a random password

        :return:
            return a random password
        :rtype: unicode
        """
        new_password = u''
        for i in range(self.config.password_length):
            # make the code more readable instead of using a long
            # list comprehension
            new_password += self.lrandom.choice(
                self.config.legal_characters).decode('utf-8')
        return new_password

    def generate_dictionary_passphrase(self):
        """
        Generates a random dictionary based passphrase

        :return:
            return a random passphrase
        :rtype: unicode
        """
        if not self.config.passphrase_dictionary:
            raise Errors.CerebrumError('Missing passphrase-dictionary')
        if len(self.dict_words) < self.config.amount_words:
            raise Errors.CerebrumError('Passphrase-dictionary not long enough')
        return u' '.join(self.lrandom.sample(self.dict_words,
                                             self.config.amount_words))
