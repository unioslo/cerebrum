#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016 University of Oslo, Norway
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
"""AMQP 0.9.1 consuming client."""

import functools

from Cerebrum.modules.event.clients.amqp_client import BaseAMQP091Client


def consumer_callback(route, content_type, body):
    """Absorbs messages silently."""
    return True


def _wrap_callback(callback_func, requeue, channel, method, header, body):
    if callback_func(method.routing_key, header.content_type, body):
        channel.basic_ack(delivery_tag=method.delivery_tag)
    else:
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=requeue)


def _cancel_callback(method_frame):
    from Cerebrum.modules.event.clients.ClientErrors import (
        ConsumerCanceledError)
    raise ConsumerCanceledError()


class ConsumingAMQP091Client(BaseAMQP091Client):
    """AMQP 0.9.1 consuming client."""

    def __init__(self, config, callback_func=consumer_callback, requeue=True):
        """Init the consuming Pika AMQP 0.9.1 wrapper client.

        :type config: AMQPClientConsumerConfig
        :param config: The configuration for the AMQP client.

        :type callback_func: function
        :param callback_func: Routing key, content type and message body.

        :type requeue: bool
        :param requeue: If failed processing should result in requeueing of
            the message (default: True).
        """
        super(ConsumingAMQP091Client, self).__init__(config)
        self.config = config
        self.callback_func = callback_func
        self.requeue = requeue

    def open(self):
        super(ConsumingAMQP091Client, self).open()
        self.channel.basic_qos(
            **{'prefetch_count': self.config.prefetch_count,
               'global_qos': self.config.qos_per_channel})

    def start(self):
        """Start consuming messages."""
        self.channel.add_on_cancel_callback(_cancel_callback)

        on_message = functools.partial(
            _wrap_callback,
            self.callback_func,
            self.requeue,
        )
        self.channel.basic_consume(
            on_message_callback=on_message,
            queue=self.config.queue,
            auto_ack=self.config.no_ack,
            consumer_tag=self.config.consumer_tag,
        )

        self.channel.start_consuming()

    def stop(self):
        """Stop consuming messages."""
        self.channel.stop_consuming()
