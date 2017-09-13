# -*- coding: utf-8 -*-

# Copyright 2017 University of Oslo, Norway
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
This module defines all necessary config for the username generator module
"""
import os

from Cerebrum.config.configuration import ConfigDescriptor, Configuration
from Cerebrum.config.loader import read, read_config
from Cerebrum.config.settings import String, NotSet


class UsernameGeneratorConfig(Configuration):
    """
    Configuration for the UsernameGenerator
    """
    encoding = ConfigDescriptor(
        String,
        default='iso-8859-1',  # The same as in Cerebrum.Account
        doc=u'The ouput encoding (default: "iso-8859-1")')


def load_config(filepath=None):
    """
    """
    config_cls = UsernameGeneratorConfig()
    if filepath:
        config_cls.load_dict(read_config(filepath))
    else:
        read(config_cls, 'username_generator')
    config_cls.validate()
    return config_cls
