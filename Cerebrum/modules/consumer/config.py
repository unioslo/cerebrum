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
Basic settings for message broker communication.
"""
import ssl

import pika

from Cerebrum.config.configuration import (
    Configuration,
    ConfigDescriptor,
    Namespace,
)
from Cerebrum.config.settings import (
    Boolean,
    FilePath,
    Iterable,
    Numeric,
    String,
)


_notset = object()


class Exchange(Configuration):
    """Configuration of a broker exchange."""

    name = ConfigDescriptor(
        String,
        minlen=1,
        doc='Exchange name',
    )
    # TODO: Choice?
    exchange_type = ConfigDescriptor(
        String,
        minlen=1,
        default='topic',
        doc='Exchange type',
    )
    durable = ConfigDescriptor(
        Boolean,
        default=True,
        doc='Set exchange to be durable',
    )


class Queue(Configuration):
    """Configuration of a broker queue."""

    name = ConfigDescriptor(
        String,
        minlen=1,
        doc='Queue name',
    )
    durable = ConfigDescriptor(
        Boolean,
        default=True,
        doc='Set queue to be durable',
    )
    exclusive = ConfigDescriptor(
        Boolean,
        default=False,
        doc='Set queue to be exclusive',
    )
    auto_delete = ConfigDescriptor(
        Boolean,
        default=False,
        doc='Set queue to be deleted',
    )


class Binding(Configuration):
    """Configuration of an exchange/queue binding."""

    exchange = ConfigDescriptor(
        String,
        minlen=1,
        doc='Exchange to bind from',
    )
    queue = ConfigDescriptor(
        String,
        minlen=1,
        doc='Queue to bind to',
    )
    routing_keys = ConfigDescriptor(
        Iterable,
        template=String(minlen=1, doc='Routing key'),
        doc='A list of routing keys to bind',
    )


class Connection(Configuration):
    """Connection params for a message broker."""

    username = ConfigDescriptor(
        String,
        default='guest',
        doc='Username for plain authentication',
    )

    password = ConfigDescriptor(
        String,
        default='guest',
        doc='Password for plain authentication',
    )

    host = ConfigDescriptor(
        String,
        default='localhost',
        doc='Hostname or IP',
    )

    port = ConfigDescriptor(
        Numeric,
        minval=0,
        maxval=0xFFFF,
        default=5672,
        doc='Port number at host',
    )

    ssl_enable = ConfigDescriptor(
        Boolean,
        default=False,
        doc='Connection/port uses ssl',
    )

    ca_file = ConfigDescriptor(
        FilePath,
        doc='Path to a ca-file in PEM format',
    )

    client_cert_file = ConfigDescriptor(
        FilePath,
        doc='Path to a client certificate in PEM format',
    )

    client_key_file = ConfigDescriptor(
        FilePath,
        doc='Path to a client key in PEM format',
    )

    virtual_host = ConfigDescriptor(
        String,
        default='/',
        doc='RabbitMQ virtual host (namespace) to use',
    )


class ConsumerConfig(Configuration):
    """MQ consumer/manager config."""

    connection = ConfigDescriptor(
        Namespace,
        config=Connection,
        doc=Connection.__doc__.strip(),
    )

    consumer_tag = ConfigDescriptor(
        String,
        default=None,
        doc='A consumer tag',
    )

    exchanges = ConfigDescriptor(
        Iterable,
        template=Namespace(config=Exchange),
        default=(),
        doc='A list of exchanges',
    )

    queues = ConfigDescriptor(
        Iterable,
        template=Namespace(config=Queue),
        default=(),
        doc='A list of queues',
    )

    bindings = ConfigDescriptor(
        Iterable,
        template=Namespace(config=Binding),
        default=(),
        doc='A list of bindings',
    )


class PublisherConfig(Configuration):
    """MQ publisher config."""

    connection = ConfigDescriptor(
        Namespace,
        config=Connection,
        doc=Connection.__doc__.strip(),
    )

    exchange = ConfigDescriptor(
        Namespace,
        config=Exchange,
        doc='An exchange to publish messages to',
    )


def get_credentials(config):
    """ Get credentials from Connection object. """
    if config.username or config.password:
        return pika.PlainCredentials(config.username, config.password)
    return None


def get_ssl_options(config):
    """ Get ssl options from Connection object. """
    if config.ssl_enable:
        ssl_context = ssl.create_default_context(cafile=config.ca_file)
        # load_cert_chain requires first param (certfile) to be a valid file
        # system path. keyfile is optional tough, so we do not need to check if
        # it is defined:
        if config.client_cert_file:
            ssl_context.load_cert_chain(config.client_cert_file,
                                        config.client_key_file)

        return pika.SSLOptions(ssl_context, config.host)
    return None


def get_connection_params(config, credentials=_notset, ssl_options=_notset):
    """
    Get pika connection from Connection object.

    :type config: Connection
    :param config: Connection configuration.

    :type credentials: NoneType, pika.PlainCredentials
    :param credentials: Override credentials from config

    :type ssl_options: NoneType, pika.SSLOptions
    :param ssl_options: Override SSL settings from config
    """
    if credentials is _notset:
        credentials = get_credentials(config)

    if ssl_options is _notset:
        ssl_options = get_ssl_options(config)

    return pika.ConnectionParameters(
        config.host,
        config.port,
        virtual_host=config.virtual_host,
        ssl_options=ssl_options,
        credentials=credentials,
    )


if __name__ == '__main__':
    print(ConsumerConfig.documentation())
    print(PublisherConfig.documentation())
