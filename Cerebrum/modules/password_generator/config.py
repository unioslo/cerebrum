# -*- coding: utf-8 -*-

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
"""
This module defines all necessary config for the password generator module
"""
import os

from Cerebrum.config.configuration import ConfigDescriptor, Configuration
from Cerebrum.config.loader import read, read_config
from Cerebrum.config.settings import Integer, FilePath, String, NotSet


class PasswordGeneratorConfig(Configuration):
    """
    Configuration for the PasswordGenerator
    """
    amount_words = ConfigDescriptor(
        Integer,
        default=5,
        minval=1,
        doc=u'Amount of dictionary-words the password phrase will contain')

    password_length = ConfigDescriptor(
        Integer,
        default=19,
        minval=1,
        doc=u'The length of the password')

    legal_characters = ConfigDescriptor(
        String,
        default=('ABCDEFGHIJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
                 '23456789!#$%&()*+,-.:;<=>?@[]^_{|}~'),
        doc=u'The characters used for password generation')

    passphrase_dictionary = ConfigDescriptor(
        FilePath,
        permission_read=True,
        # the current user should not be able to write to this file
        # permission_write=False,
        default=NotSet,
        doc=u'File-path for the passphrase-dictionary')


def load_config(filepath=None):
    """
    """
    config_cls = PasswordGeneratorConfig()
    if filepath:
        config_cls.load_dict(read_config(filepath))
    else:
        read(config_cls, 'password_generator')
    config_cls.validate()
    return config_cls
