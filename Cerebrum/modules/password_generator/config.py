# -*- coding: utf-8 -*-

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
This module defines all necessary config for the password generator module
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from Cerebrum.config import configuration as _configuration
from Cerebrum.config import loader as _loader
from Cerebrum.config import settings as _settings


DEFAULT_CONFIG_BASENAME = "password_generator"


class PasswordGeneratorConfig(_configuration.Configuration):
    """
    Legacy configuration for the PasswordGenerator, for compatibility reasons.
    """
    amount_words = _configuration.ConfigDescriptor(
        _settings.Integer,
        default=5,
        minval=1,
        doc="Number of dictionary words for passphrases",
    )

    password_length = _configuration.ConfigDescriptor(
        _settings.Integer,
        default=19,
        minval=1,
        doc="Number of characters in a regular password",
    )

    legal_characters = _configuration.ConfigDescriptor(
        _settings.String,
        default=(
            "ABCDEFGHIJKLMNPQRSTUVWXYZ"
            "abcdefghijkmnopqrstuvwxyz"
            "23456789"
            "!#$%&()*+,-.:;<=>?@[]^_{|}~"
        ),
        doc="Character set for passwords",
    )

    passphrase_dictionary = _configuration.ConfigDescriptor(
        _settings.FilePath,
        permission_read=True,
        # the current user should not be able to write to this file
        # permission_write=False,
        default=_settings.NotSet,
        doc="Path to a file with words for passphrases",
    )


def load_config(filename=None):
    """
    Load the password generator config.

    :param str filename:
        If given, read the config from this file rather than
        `<config-path>/password_generator.<ext>`
    """
    config = PasswordGeneratorConfig()
    if filename:
        config.load_dict(_loader.read_config(filename))
    else:
        _loader.read(config, DEFAULT_CONFIG_BASENAME)
    config.validate()
    return config
