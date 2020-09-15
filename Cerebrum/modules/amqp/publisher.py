# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
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
import pika
import pika.exceptions


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

    @property
    def connection(self):
        """ Pika connection - must be explicitly :meth:`.open()`-ed. """
        return self._connection

    @property
    def channel(self):
        """ Pika channel - created on request. """
        if not self.connection:
            raise RuntimeError('Connection already open')
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

    def publish(self,
                exchange,
                routing_key,
                message,
                content_type='text/plain',
                delivery_mode=2):
        props = pika.BasicProperties(content_type=content_type,
                                     delivery_mode=delivery_mode)
        try:
            self.channel.basic_publish(exchange, routing_key, message, props)
        except pika.exceptions.NackError:
            return False
        else:
            return True


class Publisher(object):
    """
    A message publisher context.

    Example:
        conn = get_connection_params(config.Connection())

        with Publisher(conn) as publish:
            if publish('my_exchange', 'example.key', 'hello, world!'):
                print('success!')
            else:
                print('oops, no ack!')

    """

    def __init__(self, connection_params):
        self._client = BlockingClient(connection_params)

    def __enter__(self):
        if self._client.closed:
            self._client.open()
        return self

    def __exit__(self, exc_type, exc, trace):
        self._client.close()

    def __call__(self, *args, **kwargs):
        try:
            self._client.publish(*args, **kwargs)
        except pika.exceptions.NackError:
            return False
        else:
            return True
