#! /usr/bin/env python
# encoding: utf-8
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
>>> c = amqp_client.AMQP091Client({'host': 'tcp://127.0.0.1:6161',
...                               'exchange': '/queue/test',
...                               'transaction': True})
>>> c.publish(['ost', 'fisk'])
>>> c.publish('kolje')
>>> c.commit()
"""

import json

import pika

# from Cerebrum.modules.event_publisher import ClientErrors


class AMQP091Client(object):
    def __init__(self, config):
        """Init the Pika AMQP 0.9.1 wrapper client.

        :type config: dict
        :param config: The configuration for the AMQP client.
            I.e. {'host': 'tcp://127.0.0.1',
                  'exchange-name': 'min_exchange',
                  'exchange-type': 'topic'}
        """
        self.config = config
        self.exchange = self.config.get('exchange-name')
        self.transactions_enabled = self.config.get('transactions-enabled')
        self.transaction = None  # Keep track of if we are in a transaction
        # Define potential credentials
        if self.config.get('username', None):
            from Cerebrum.Utils import read_password
            cred = pika.credentials.PlainCredentials(
                self.config.get('username'),
                read_password(self.config.get('username'),
                              self.config.get('hostname')))
            ssl_opts = None
        elif self.config.get('cert', None):
            cred = pika.credentials.ExternalCredentials()
            ssl_opts = {'keyfile': self.config.get('cert').get('client-key'),
                        'certfile': self.config.get('cert').get('client-cert')}
        else:
            ssl_opts = cred = None
        # Create connection-object
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=self.config.get('hostname'),
                port=int(self.config.get('port')),
                virtual_host=self.config.get('virtual-host'),
                credentials=cred,
                ssl=self.config.get('tls-on'),
                ssl_options=ssl_opts))
        # Set up channel
        self.channel = self.connection.channel()
        # Declare exchange
        self.channel.exchange_declare(
            exchange=self.exchange,
            exchange_type=self.config.get('exchange-type'))
        if self.transactions_enabled:
            # Start transaction
            self.channel.tx_select()
            self.transaction = True
        else:
            # Ensure that messages are recieved by the broker
            self.channel.confirm_delivery()
            self.transaction = 'Never'

    def publish(self, messages, omit_transaction=False, durable=True):
        """Publish a message to the exchange.

        :type message: string or list of strings.
        :param message: The message(s) to publish.

        :type omit_transaction: bool
        :param omit_transaction: Set to True if you would like to publish a
            message outside a transaction.

        :type durable: bool
        :param durable: If this message should be durable.
        """
        # TODO: Implement support for publishing outside transaction? For this
        # to work, we must create a new channel.
        if isinstance(messages, (basestring, dict)):
            messages = [messages]
        for msg in messages:
            event_type = (
                '%s:%s' % (msg.get('category'), msg.get('change')) if
                msg.get('change', None) else msg.get('category'))
            # TODO: Should we handle exceptions?
            if self.channel.basic_publish(exchange=self.exchange,
                                          routing_key=event_type,
                                          body=json.dumps(msg),
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
                # TODO: Should we rather raise an exception?
                return False

    def __del__(self):
        self.connection.close()

    def close(self):
        """Close the connection."""
        self.connection.close()

    def start_transaction(self):
        assert not self.transaction, "Can't start transaction twice"
        assert self.transaction != 'Never', ("Can't start transaction, "
                                             "publisher confirm on")
        self.channel.tx_select()

    def commit(self):
        """Commit the current transaction."""
        assert self.transaction, "Can't commit outside transaction"
        assert self.transaction != 'Never', ("Can't commit transaction, "
                                             "publisher confirm on")
        self.channel.tx_commit()

    def rollback(self):
        """Roll back the current transaction."""
        assert self.transaction, "Can't roll back outside transaction"
        assert self.transaction != 'Never', ("Can't roll back transaction, "
                                             "publisher confirm on")
        self.channel.tx_rollback()
