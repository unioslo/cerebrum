# -*- coding: utf-8 -*-
#
# Copyright 2020-2023 University of Oslo, Norway
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
Simple blocking message publisher.

This module contains a basic "client" (pika connection wrapper) that hides away
connection and channel management.

This client is mainly suitable for short-lived connections, where we don't
expect the server to close the channel or connection during operation.


Example
-------
A minimal example to connect to a RabbitMQ server running default config:

::

    conf = config.Connection()
    client = BlockingClient(config.get_connection_params(conf))
    client.publish('exchange', 'routing.key', 'message!')

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import logging

import pika
import pika.exceptions

logger = logging.getLogger(__name__)


class BlockingClient(object):
    """
    A blocking pika connection wrapper.
    """
    # This "client" currently only supports publishing.  Consider moving
    # it to another module (.client?) if other ops are added.

    def __init__(self, connection_params):
        self._channel = None
        self._connection = None
        self.connection_params = connection_params

    def __enter__(self):
        if self.closed:
            self.open()
        return self

    def __exit__(self, exc_type, exc, trace):
        self.close()

    @property
    def connection(self):
        """ Pika connection - must be explicitly :meth:`.open()`-ed. """
        return self._connection

    @property
    def channel(self):
        """ Pika channel - created on request. """
        if not self.connection:
            raise RuntimeError('Connection not open')
        if not self._channel:
            self._channel = c = self.connection.channel()
            # TODO: Should this be configurable?
            c.confirm_delivery()
        return self._channel

    @property
    def closed(self):
        return self.connection is None

    def open(self):
        if self.connection:
            raise RuntimeError('Connection already open')

        self._connection = pika.BlockingConnection(self.connection_params)

    def close(self):
        try:
            self._connection.close()
        except pika.exceptions.ConnectionClosed:
            pass
        self._connection = None
        self._channel = None

    def publish(self,
                exchange_name,
                routing_key,
                message,
                content_type='text/plain',
                delivery_mode=2):
        props = pika.BasicProperties(content_type=content_type,
                                     delivery_mode=delivery_mode)
        self.channel.basic_publish(exchange_name, routing_key, message, props)

    def declare_exchange(self, exchange):
        """
        Assert that a given exchange exists.

        :type exchange: Cerebrum.modules.amqp.config.Exchange
        """
        self.channel.exchange_declare(
            exchange=exchange.name,
            exchange_type=exchange.exchange_type,
            durable=exchange.durable)
        logger.info('exchange: %r, type=%r, durable=%r',
                    exchange.name, exchange.exchange_type, exchange.durable)
