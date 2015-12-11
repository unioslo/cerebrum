#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2015 University of Oslo, Norway
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
""" This module defines all neccessary config for the CIM integration. """

from Cerebrum.config.configuration import Configuration
from Cerebrum.config.configuration import ConfigDescriptor
from Cerebrum.config.configuration import Namespace

from Cerebrum.config.loader import read, read_config

from Cerebrum.config.settings import Setting
from Cerebrum.config.settings import String
from Cerebrum.config.settings import Boolean


def mixin_config(attr, cls):
    return type('_ConfigMixin',
                (Configuration, ),
                {attr: ConfigDescriptor(Namespace, config=cls,)})


class CimClientConfig(Configuration):
    """Configuration for the CIM WS client."""
    api_url = ConfigDescriptor(
        String,
        default=None,
        doc="URL to the JSON API. Will be suffixed with endpoints.")

    dry_run = ConfigDescriptor(
        Boolean,
        default=True,
        doc="Send requests to web service with dry run mode enabled?")


class CimEventConfig(Configuration):
    """Configuration for the CIM event handler."""
    pass


class CimConfig(
        mixin_config('client', CimClientConfig),
        mixin_config('event', CimEventConfig),
        Configuration):
    pass


def load_config(filepath=None):
    config_cls = CimConfig()
    if filepath:
        config_cls.load_dict(read_config(filepath))
    else:
        read(config_cls, 'cim')
    config_cls.validate()
    return config_cls
