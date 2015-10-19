#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

""" Wrapper of the pika AMQP 0.9.1 client.

# Connect and publish messages with the client:
>>> import amqp_client
>>> c = amqp_client.AMQP091Client({'hostname': '127.0.0.1',
...                                'exchange': '/queue/test',
...                                'port': 6161)
>>> c.publish(['ost', 'fisk'])
>>> c.publish('kolje')
>>> c.commit()
"""

import json

import pika

from Cerebrum.modules.event_publisher import ClientErrors


class AMQP091Client(object):
    """
    """

    def __init__(self, config):
        """Init the Pika AMQP 0.9.1 wrapper client.

        :type config: dict
        :param config: The configuration for the AMQP client.
            I.e. {'hostname': '127.0.0.1',
                  'exchange-name': 'min_exchange',
                  'exchange-type': 'topic'}
        """
        if not isinstance(config, dict):
            raise TypeError('config must be a dict')
        self.config = config
        self.exchange = self.config.get('exchange-name')
        # Define potential credentials
        if self.config.get('username'):
            from Cerebrum.Utils import read_password
            cred = pika.credentials.PlainCredentials(
                self.config.get('username'),
                read_password(self.config.get('username'),
                              self.config.get('hostname')))
            ssl_opts = None
        elif self.config.get('cert'):
            cred = pika.credentials.ExternalCredentials()
            ssl_opts = {'keyfile': self.config.get('cert').get('client-key'),
                        'certfile': self.config.get('cert').get('client-cert')}
        else:
            raise ClientErrors.ConfigurationFormatError(
                "Configuration contains neither 'username' or 'cert' value")
        # Create connection-object
        try:
            err_msg = 'Ivalid connection parameters'
            conn_params = pika.ConnectionParameters(
                host=self.config.get('hostname'),
                port=int(self.config.get('port')),
                virtual_host=self.config.get('virtual-host'),
                credentials=cred,
                ssl=self.config.get('tls-on'),
                ssl_options=ssl_opts)
            err_msg = 'Unable to connect to broker'
            self.connection = pika.BlockingConnection(conn_params)
        except Exception as e:
            raise ClientErrors.ConnectionError('{0}: {1}'.format(err_msg, e))
        # Set up channel
        self.channel = self.connection.channel()
        # Declare exchange
        self.channel.exchange_declare(
            exchange=self.exchange,
            exchange_type=self.config.get('exchange-type'),
            durable=self.config.get('exchange-durable'))
        # Ensure that messages are recieved by the broker
        self.channel.confirm_delivery()

    def publish(self, messages, durable=True):
        """Publish a message to the exchange.

        :type message: dict or list of dicts.
        :param message: The message(s) to publish.

        :type durable: bool
        :param durable: If this message should be durable.
        """
        # TODO: Implement support for publishing outside transaction? For this
        # to work, we must create a new channel.
        if isinstance(messages, dict):
            messages = [messages]
        elif not isinstance(messages, list):
            raise TypeError('messages must be a dict or a list of dicts')
        for msg in messages:
            if not isinstance(msg, dict):
                raise TypeError('messages must be a dict or a list of dicts')
            try:
                err_msg = 'Could not generate routing key'
                event_type = '.'.join(
                    filter(lambda y: y is not None,
                           map(lambda x: msg.get(x), ('category',
                                                      'meta_object_type',
                                                      'change'))))
                err_msg = ('Could not generate'
                           ' application/json content from message')
                msg_body = json.dumps(msg)
            except Exception as e:
                raise ClientErrors.MessageFormatError('{0}: {1}'.format(
                    err_msg,
                    e))
            try:
                if self.channel.basic_publish(
                        exchange=self.exchange,
                        routing_key=event_type,
                        body=msg_body,
                        properties=pika.BasicProperties(
                            # Delivery mode:
                            # 1: Non-persistent
                            # 2: Persistent
                            delivery_mode=2,
                            content_type='application/json'),
                        # Makes publish return false if
                        # message not published
                        mandatory=True,
                        # TODO: Should we enable immediate?
                ):
                    return True
                else:
                    raise Exception('Broker did not confirm message delivery')
            except Exception as e:
                raise ClientErrors.MessagePublishingError(
                    'Unable to publish message: {0}'.format(e))

    def __del__(self):
        self.connection.close()

    def close(self):
        """Close the connection."""
        self.connection.close()
