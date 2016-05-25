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
"""AMQP 0.9.1 consuming client."""

import uuid

from Cerebrum.modules.event.clients.amqp_client import BaseAMQP091Client


def consumer_callback(channel, method, header, body):
    """Absorbs messages silently."""
    channel.basic_ack(delivery_tag=method.delivery_tag)


class ConsumingAMQP091Client(BaseAMQP091Client):
    """AMQP 0.9.1 consuming client."""

    def __init__(self, config, callback_func=consumer_callback):
        """Init the consuming Pika AMQP 0.9.1 wrapper client.

        :type config: dict
        :param config: The configuration for the AMQP client.
            I.e. {'hostname': '127.0.0.1',
                  'exchange-name': 'min_exchange',
                  'exchange-type': 'topic'}
        """
        super(ConsumingAMQP091Client, self).__init__(config)

        self.channel.basic_consume(callback_func,
                                   queue=config.get('queue'),
                                   no_ack=config.get('no_ack', False),
                                   consumer_tag=config.get('consumer_tag',
                                                           uuid.uuid4()))
        self.channel.start_consuming()
