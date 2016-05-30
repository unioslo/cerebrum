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
""" This module defines all necessary config for the consuming AMQP client. """

import uuid

from Cerebrum.modules.event.clients.amqp_client_config import (
    BaseAMQPClientConfig,)

from Cerebrum.config.loader import read, read_config
from Cerebrum.config.configuration import ConfigDescriptor


from Cerebrum.config.settings import (Boolean,
                                      String)


class AMQPClientConsumerConfig(BaseAMQPClientConfig):
    u"""Configuration for the consuming AMQP client."""
    queue = ConfigDescriptor(String,
                             default=u"cerebrum",
                             doc=u"Queue to be consumed")

    no_ack = ConfigDescriptor(Boolean,
                              default=False,
                              doc=u"Do not ack messages")

    consumer_tag = ConfigDescriptor(String,
                                    default=unicode(uuid.uuid4()),
                                    doc=u"A tag representing this consumer")


def load_config(filepath=None, consumer_name=None):
    u"""Load config.

    Load config from filepath or the config associated with consumer_name.

    Defaults to consumer_config.json

    :type filepath: str
    :param filepath: The filepath to load

    :type consumer_name: str
    :param consumer_name: Load <consumer_name>.json"""
    config_cls = AMQPClientConsumerConfig()
    if filepath:
        config_cls.load_dict(read_config(filepath))
    elif consumer_name:
        read(config_cls, consumer_name)
    else:
        read(config_cls, 'consumer_config')
    config_cls.validate()
    return config_cls
