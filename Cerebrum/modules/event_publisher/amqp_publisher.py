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

""" Wrapper of the pika AMQP 0.9.1 client.

This client is hard coded to publish persistent messages with content-type
'application/json'.

Connect and publish messages with the client:

>>> from Cerebrum.modules.event_publisher.config import load_publisher_config
>>> from Cerebrum.modules.event_publisher.amqp_publisher import (
...     AMQP091Publisher, )
>>> c = AMQP091Publisher(load_config())
>>> c.publish('my_routing_key', '{"fisk": ["hyse", "kolje"]}')
>>> c.close()
"""
import json
import pika
import six

from Cerebrum.modules.event.clients import ClientErrors
from Cerebrum.modules.event.clients import amqp_client
from Cerebrum.modules.event.clients import amqp_client_config

from Cerebrum.config.configuration import (Namespace,
                                           Configuration,
                                           ConfigDescriptor)
from Cerebrum.config.settings import (Boolean, String)


DELIVERY_NON_PERSISTENT = 1
DELIVERY_PERSISTENT = 2

CONTENT_TYPE = 'application/json'


class AMQP091Publisher(amqp_client.BaseAMQP091Client):
    """AMQP 0.9.1 client wrapper usable for publishing messages."""

    def __init__(self, config):
        """Init the Pika AMQP 0.9.1 wrapper client.

        :type config: AMQPClientPublisherConfig
        :param config: The configuration for the AMQP client.
        """
        super(AMQP091Publisher, self).__init__(config)
        self.exchange_name = config.exchange_name
        self.exchange_type = config.exchange_type
        self.exchange_durable = config.exchange_durable

    def open(self):
        super(AMQP091Publisher, self).open()
        # Declare exchange
        self.channel.exchange_declare(
            exchange=self.exchange_name,
            exchange_type=self.exchange_type,
            durable=self.exchange_durable)
        # Ensure that messages are recieved by the broker
        self.channel.confirm_delivery()

    def publish(self, routing_key, message, durable=True):
        """Publish a message to the exchange.

        :type messages: dict or list of dicts.
        :param messages: The message(s) to publish.

        :type durable: bool
        :param durable: If this message should be durable.
        """
        try:
            routing_key = routing_key or 'unknown'

            if isinstance(message, basestring):
                # Validate any previously stored json strings?
                # message = json.loads(message)
                msg_body = six.text_type(message)
            else:
                msg_body = json.dumps(message)
        except Exception as e:
            raise ClientErrors.MessageFormatError(
                'Unable to format message: {0!r}'.format(e))
        try:
            self.channel.basic_publish(
                exchange=self.exchange_name,
                routing_key=routing_key,
                body=msg_body,
                properties=pika.BasicProperties(
                    delivery_mode=DELIVERY_PERSISTENT,
                    content_type=CONTENT_TYPE),
                mandatory=False)
        except pika.exceptions.NackError as e:
            raise ClientErrors.MessagePublishingError(
                'Unable to publish message: {0!r}'.format(e))


class PublisherConfig(amqp_client_config.BaseAMQPClientConfig):
    u"""Configuration for the Publishing AMQP client."""

    class PublisherClass(Configuration):
        mod = ConfigDescriptor(
            String,
            default=AMQP091Publisher.__module__,
            doc="Publisher module to use for publishing events")
        cls = ConfigDescriptor(
            String,
            default=AMQP091Publisher.__name__,
            doc="Publisher class to use for publishing events")

    publisher_class = ConfigDescriptor(
        Namespace,
        config=PublisherClass)

    exchange_type = ConfigDescriptor(
        String,
        default=u"topic",
        doc=u"The exchange type")

    exchange_durable = ConfigDescriptor(
        Boolean,
        default=True,
        doc=u"Whether the exchange is durable or not")

    exchange_name = ConfigDescriptor(
        String,
        default=u"api_events",
        doc=u"The name of the exchange")
