#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015-2016 University of Oslo, Norway
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

""" Wrapper base of the pika AMQP 0.9.1 client.

# Connect and publish messages with the client:
>>> import amqp_client
>>> c = amqp_client.AMQP091Client({'hostname': '127.0.0.1',
...                                'exchange': '/queue/test',
...                                'port': 6161)
>>> c.publish(['ost', 'fisk'])
>>> c.publish('kolje')
>>> c.commit()
"""

import pika

from Cerebrum.modules.event.clients import ClientErrors


class BaseAMQP091Client(object):
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
