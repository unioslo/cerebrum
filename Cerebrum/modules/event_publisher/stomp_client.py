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

""" Wrapper of the stompest STOMP client.

To test:
# Start a simple mq for testing
$ pip install coilmq
$ coilmq -b 127.0.0.1 -p 6161 --debug

# Connect and publish messages with the client:
>>> import stomp_client
>>> c = stomp_client.StompClient({'host': 'tcp://127.0.0.1:6161',
...                               'queue': '/queue/test',
...                               'transaction': True})
>>> c.publish(['ost', 'fisk'])
>>> c.publish('kolje')
>>> c.commit()
"""

import uuid
import json
import six

from stompest.config import StompConfig
from stompest.protocol import StompSpec
from stompest.sync import Stomp
from stompest import error

from Cerebrum.modules.event_publisher import ClientErrors
from . import scim


class StompClient(object):
    def __init__(self, config):
        """Init the Stompest wrapper client.

        :type config: dict
        :param config: The configuration for the STOM client.
            I.e. {'host': 'tcp://127.0.0.1',
                  'queue': '/queue/test',
                  'transaction': True,
                  'username': 'my_username',
                  'password': 'fido5'}
             The transaction attribute defines if messages should be published
             in transactions.
        """
        self.host = config['host']
        self.queue = config['queue']
        self.transactions_enabled = config['transaction']
        self.transaction = None

        auth_header = {}
        if 'username' in config and 'password' in config:
            auth_header.update(
                {StompSpec.LOGIN_HEADER: config['username'],
                 StompSpec.PASSCODE_HEADER: config['password']})

        self.client = Stomp(StompConfig(self.host))
        try:
            self.client.connect(headers=auth_header)
        except (error.StompConnectTimeout, error.StompProtocolError) as e:
            raise ClientErrors.ConnectionError(
                "Could not connect to broker: %s" % e)

    def close(self):
        """Close the connection."""
        try:
            self.client.disconnect()
        except error.StompConnectionError as e:
            raise ClientErrors.ConnectionError(
                "Could not close connection: %s" % e)

    def publish(self, messages, omit_transaction=False, durable=True):
        """Publish a message to the queue.

        :type message: string or list of strings.
        :param message: The message(s) to publish.

        :type omit_transaction: bool
        :param omit_transaction: Set to True if you would like to publish a
            message outside a transaction.

        :type durable: bool
        :param durable: If this message should be durable.
        """
        if omit_transaction:
            header = None
        elif self.transactions_enabled:
            if not self.transaction:
                self.transaction = six.text_type(uuid.uuid4())
                try:
                    self.client.begin(transaction=self.transaction)
                except error.StompProtocolError as e:
                    raise ClientErrors.ProtocolError(
                        "Could not start transaction: %s" % e)
            header = {StompSpec.TRANSACTION_HEADER: self.transaction,
                      'durable': 'true' if durable else 'false'}
        else:
            header = None

        if isinstance(messages, (basestring, dict, scim.Event)):
            messages = [messages]
        for msg in messages:
            try:
                if isinstance(msg, dict):
                    del msg['routing-key']
                    msg = json.dumps(msg)
                elif isinstance(msg, scim.Event):
                    msg = json.dumps(msg.get_payload())

                self.client.send(self.queue,
                                 msg,
                                 header)
            except error.StompConnectionError as e:
                raise ClientErrors.ConnectionError(
                    "Could not publish '%s' to broker: %s" % (msg, e))

    def commit(self):
        """Commit the current transaction."""
        if self.transaction:
            self.client.commit(transaction=self.transaction)
            self.transaction = None

    def rollback(self):
        """Roll back (ABORT) the current transaction."""
        if self.transaction:
            self.client.abort(transaction=self.transaction)
            self.transaction = None
