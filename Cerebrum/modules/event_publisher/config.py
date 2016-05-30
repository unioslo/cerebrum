#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
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
""" This module defines all necessary config for the publishing AMQP client.
"""

from Cerebrum.modules.event.clients.amqp_client_config import (
    BaseAMQPClientConfig,)

from Cerebrum.config.loader import read, read_config
from Cerebrum.config.configuration import ConfigDescriptor

from Cerebrum.config.settings import (Boolean,
                                      String)


class AMQPClientPublisherConfig(BaseAMQPClientConfig):
    u"""Configuration for the Publishing AMQP client."""
    exchange_type = ConfigDescriptor(String,
                                     default=u"topic",
                                     doc=u"The exchange type")

    exchange_durable = ConfigDescriptor(
        Boolean,
        default=True,
        doc=u"Whether the exchange is durable or not")

    exchange_name = ConfigDescriptor(String,
                                     default=u"api_events",
                                     doc=u"The name of the exchange")


def load_config(filepath=None):
    u"""Load the config in filepath.

    defaults to event_publisher.json"""
    config_cls = AMQPClientPublisherConfig()
    if filepath:
        config_cls.load_dict(read_config(filepath))
    else:
        read(config_cls, 'event_publisher')
    config_cls.validate()
    return config_cls
