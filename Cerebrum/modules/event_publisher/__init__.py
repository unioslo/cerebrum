#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015-2017 University of Oslo, Norway
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
""" Event Publisher.

This sub-package contains all the neccessary parts needed to store temporary
events in the database, and to publish them to a Message Broker.

This module exposes two parts: An AMQP 0-9-1 client, and a SCIM-formatter.
"""
from Cerebrum.Utils import Factory
from .config import load_publisher_config
from .config import load_formatter_config
from .scim import ScimFormatter

__version__ = '1.0'


# Hard coded value from the SQL NOTIFY trigger
EVENT_CHANNEL = 'event_publisher'


def get_client(config=None):
    """
    Instantiate publishing client.

    Instantiated trough the defined config.
    """
    config = config or load_publisher_config()
    import_string = '{0}/{1}'.format(config.publisher_class.mod,
                                     config.publisher_class.cls)
    publisher_class = Factory.make_class('EventPublisher', [import_string, ])
    return publisher_class(config)


def get_formatter(config=None):
    config = config or load_formatter_config()
    return ScimFormatter(config)
