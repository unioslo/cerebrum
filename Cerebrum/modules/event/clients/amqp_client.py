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

# Connect with the client:
>>> from Cerebrum.modules.event.clients.config import load_config
>>> from Cerebrum.modules.event.clients.amqp_client import (
...     BaseAMQP091Client)
>>> c = BaseAMQP091Client(load_config())
>>> c.close()
"""

import pika

from Cerebrum.modules.event.clients import ClientErrors


class BaseAMQP091Client(object):
    """AMQP 0.9.1 client implementing open/close of connections."""

    def __init__(self, config):
        """Init the Pika AMQP 0.9.1 wrapper client.

        :type config: BaseAMQPClientConfig
        :param config: The configuration for the AMQP client.
        """
        # Define potential credentials
        if config.username:
            from Cerebrum.Utils import read_password
            cred = pika.credentials.PlainCredentials(
                config.username,
                read_password(config.username,
                              config.hostname))
            ssl_opts = None
        else:
            raise ClientErrors.ConfigurationFormatError(
                "Configuration contains neither 'username' or 'cert' value")
        # Create connection-object
        try:
            err_msg = 'Invalid connection parameters'
            conn_params = pika.ConnectionParameters(
                host=config.hostname,
                port=config.port,
                virtual_host=config.virtual_host,
                credentials=cred,
                ssl=config.tls_on,
                ssl_options=ssl_opts)
            err_msg = 'Unable to connect to broker'
            self.connection = pika.BlockingConnection(conn_params)
        except Exception as e:
            raise ClientErrors.ConnectionError('{0}: {1}'.format(err_msg, e))
        # Set up channel
        self.channel = self.connection.channel()

    def close(self):
        """Close the connection."""
        self.connection.close()
