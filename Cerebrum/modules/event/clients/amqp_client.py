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
""" Wrapper base of the pika AMQP 0.9.1 client.

# Connect with the client:
>>> from Cerebrum.modules.event.clients.config import load_config
>>> from Cerebrum.modules.event.clients.amqp_client import (
...     BaseAMQP091Client)
>>> c = BaseAMQP091Client(load_config())
>>> c.close()
"""
import ssl

import pika
import pika.exceptions

from Cerebrum.Utils import read_password
from Cerebrum.modules.event.clients import ClientErrors


def make_credentials(username, hostname):
    return pika.credentials.PlainCredentials(
        username,
        read_password(username, hostname))


class BaseAMQP091Client(object):
    """AMQP 0.9.1 client implementing open/close of connections."""

    def __init__(self, config):
        """Init the Pika AMQP 0.9.1 wrapper client.

        :type config: BaseAMQPClientConfig
        :param config: The configuration for the AMQP client.
        """
        # Define potential credentials
        if config.username:
            cred = make_credentials(config.username, config.hostname)
        else:
            raise ClientErrors.ConfigurationFormatError(
                "Configuration contains neither 'username' or 'cert' value")

        if config.tls_on:
            ssl_context = ssl.create_default_context()
            ssl_opts = pika.SSLOptions(ssl_context, config.hostname)
        else:
            ssl_opts = None

        # Create connection-object
        try:
            self.conn_params = pika.ConnectionParameters(
                host=config.hostname,
                port=config.port,
                virtual_host=config.virtual_host,
                credentials=cred,
                ssl_options=ssl_opts)
        except Exception as e:
            raise ClientErrors.ConnectionError(
                'Invalid connection parameters: {}'.format(e))
        self.channel = self.connection = None

    def open(self):
        """Open connection"""
        try:
            self.connection = pika.BlockingConnection(self.conn_params)
        except Exception as e:
            raise ClientErrors.ConnectionError(
                'Unable to connect to broker: {} {}'.format(type(e), str(e)))
        # Set up channel
        self.channel = self.connection.channel()

    def __enter__(self):
        if self.channel is None or not self.connection.is_open:
            self.open()
        return self

    def close(self):
        """Close the connection."""
        try:
            self.connection.close()
        except pika.exceptions.ConnectionClosed:
            pass

    def __exit__(self, exc_type, exc, trace):
        if self.connection is not None and self.connection.is_open:
            self.close()
