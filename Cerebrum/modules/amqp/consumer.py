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
Simple callback/async message broker consumer.

Example
-------
A minimal example to connect to a RabbitMQ server running default config:

::

    conf = config.ConsumerConfig()
    consume = Manager(
        config.get_connection_params(conf.connection),
        demo_callback,
        ChannelSetup(
            exchanges=conf.exchanges,
            queues=conf.queues,
            bindings=conf.bindings,
            flags=ChannelSetup.Flags.ALL,
            consumer_tag_prefix=conf.consumer_tag,
        ),
    )
    consume.run()

"""
import functools
import logging
import time
import uuid

import pika

logger = logging.getLogger(__name__)


def declare_exchange(channel, exchange):
    """
    Assert that a given exchange exists.

    :type channel: pika.channel.Channel
    :type exchange: Cerebrum.modules.amqp.config.Exchange
    """

    def on_ok(result):
        logger.info('exchange: %r, type=%r, durable=%r',
                    exchange.name, exchange.exchange_type, exchange.durable)

    channel.exchange_declare(
        exchange=exchange.name,
        exchange_type=exchange.exchange_type,
        durable=exchange.durable,
        callback=on_ok)


def declare_queue(channel, queue):
    """
    Assert that a given queue exists.

    :type channel: pika.channel.Channel
    :type queue: Cerebrum.modules.amqp.config.Queue
    """

    def on_ok(result):
        logger.info('queue: %r, durable=%r, exclusive=%r, delete=%r',
                    queue.name, queue.durable, queue.exclusive,
                    queue.auto_delete)

    channel.queue_declare(
        queue=queue.name,
        durable=queue.durable,
        exclusive=queue.exclusive,
        auto_delete=queue.auto_delete,
        callback=on_ok)


def bind_queue(channel, binding):
    """
    Assert that a given set of bindings exists.

    :type channel: pika.channel.Channel
    :type queue: Cerebrum.modules.amqp.config.Binding
    """

    def on_ok(key, result):
        logger.info('binding: %r, exchange=%r, queue=%r',
                    key, binding.exchange, binding.queue)

    for rk in binding.routing_keys:
        channel.queue_bind(
            queue=binding.queue,
            exchange=binding.exchange,
            routing_key=rk,
            callback=functools.partial(on_ok, rk))


class ChannelSetup(object):
    """
    Instructions for channel setup.

    This class implements the channel setup for the :py:class:`.Manager` -- it
    basically wraps configuration (exchanges, queues, bindings) and ensures
    that the required channel declarations are performed (e.g. on channel
    open).
    """

    class Flags(object):
        """
        Supported channel setup steps.

        EXCHANGE
            Declare exchanges.

        QUEUE
            Declare queues.

        BIND
            Set up queue bindings.

        CONSUME
            Start consuming messages.
        """
        CONSUME = 1 << 0
        BIND = 1 << 1
        QUEUE = 1 << 2
        EXCHANGE = 1 << 3

        ALL = EXCHANGE | QUEUE | BIND | CONSUME

        @classmethod
        def to_string(cls, flags):
            """Format flags to human readable format"""
            return ' | '.join(
                attr
                for attr in ('EXCHANGE', 'QUEUE', 'BIND', 'CONSUME')
                if flags & getattr(cls, attr))

    def __init__(self,
                 exchanges=None,
                 queues=None,
                 bindings=None,
                 flags=Flags.ALL,
                 consumer_tag_prefix=None):
        """
        :type exchanges: list, set
        :param exchanges:
            A sequence of exchanges
            (:py:class:`Cerebrum.modules.consumer.config.Exchange` objects) to
            declare during startup.

        :type queues: list, set
        :param queues:
            A sequence of queues
            (:py:class:`Cerebrum.modules.consumer.config.Queue` objects) to
            declare during startup.

        :type bindings: list, set
        :param bindings:
            A sequence of bindings
            (:py:class:`Cerebrum.modules.consumer.config.Binding` objects) to
            set up during startup.

        :type flags: int
        :param flags:
            Which steps to perform during setup.

        :param consumer_tag_prefix:
            A prefix to use for consumer tags.
        """
        self.exchanges = exchanges or ()
        self.queues = queues or ()
        self.bindings = bindings or ()
        self.flags = flags
        self.consumer_tag_prefix = consumer_tag_prefix

    @property
    def flags(self):
        """ Steps to execute on setup. """
        return self._flags

    @flags.setter
    def flags(self, value):
        if value & ~self.Flags.ALL:
            raise ValueError('Unknown flags: %s (%s)' %
                             (format(value & ~self.Flags.ALL, '04b'),
                              format(value, '04b')))
        self._flags = value

    def make_consumer_tag(self):
        """ Make a new consumer tag. """
        if self.consumer_tag_prefix is not None:
            return '{}-{:08x}'.format(
                self.consumer_tag_prefix,
                int(uuid.uuid4()) % (2 ** 32))
        else:
            return str(uuid.uuid4())

    def __call__(self, channel, on_message):
        """
        Run channel setup.

        :param channel:
        :param on_message:
            Message callback function to set up for the CONSUME step.
        """
        flags = self.flags
        logger.debug('setup: %s on channel %d',
                     self.Flags.to_string(flags), channel)

        if not flags:
            logger.warning('no setup!')

        if flags & self.Flags.EXCHANGE:
            logger.debug('setup: EXCHANGE (%r)', self.exchanges)
            for e in self.exchanges:
                declare_exchange(channel, e)

        if flags & self.Flags.QUEUE:
            logger.debug('setup: QUEUE (%r)', self.queues)
            for e in self.queues:
                declare_queue(channel, e)

        if flags & self.Flags.BIND:
            logger.debug('setup: BIND (%r)', self.bindings)
            for e in self.bindings:
                bind_queue(channel, e)
            # TODO: Should we add a step to set up qos/prefetch?
            # channel.basic_qos(prefetch_count=1)

        if flags & self.Flags.CONSUME:
            logger.debug('setup: CONSUME')

            for queue in set(x.queue for x in self.bindings):
                return_tag = channel.basic_consume(
                    queue=queue,
                    on_message_callback=on_message,
                    auto_ack=False,
                    consumer_tag=self.make_consumer_tag())
                logger.info('consuming queue=%r with consumer_tag=%r',
                            queue, return_tag)


class Manager(object):
    """
    Pika consumer/async manager.
    """

    reconnect_timeout = 5

    # TODO: Replace exchanges/queue/bindings with a single setup callable
    def __init__(self, connection_params, handler, setup):
        """
        :type connection_params: pika.ConnectionParameters
        :param connection_params:
            Broker connection settings.

        :type handler: callable
        :param handler:
            Callback to run when a message is received.

            Signature ``handle(channel, method, properties, body)``.

        :type setup: callable
        :param setup:
            Callback to perform on channel open.

            Signature ``setup(channel, on_message)``
        """

        self.connection_params = connection_params

        self.consume = handler
        self._setup = setup

        self.stopped = False

        self._connection = None
        self._channel = None

    #
    # connection management
    #

    def connect(self):
        """connect to rabbitmq and configure."""
        params = self.connection_params
        logger.info('connecting to %r', params)
        return pika.SelectConnection(
            parameters=params,
            on_open_callback=self.on_connection_open,
            on_open_error_callback=self.on_connection_open_error,
        )

    def reconnect(self):
        # This is the old connection IOLoop instance, stop its ioloop
        self._connection.ioloop.stop()

        if not self.stopped:
            # Create a new connection
            self._connection = self.connect()

            # There is now a new connection, needs a new ioloop to run
            self._connection.ioloop.start()

    def close_connection(self):
        """This method closes the connection to RabbitMQ."""
        logger.info('closing connection')
        self._connection.close()

    def on_connection_open(self, connection):
        """ connection callback -> open_channel

        :type connection: pika.SelectConnection
        """
        logger.info('connection opened')
        logger.debug('add on_close_callback')
        connection.add_on_close_callback(self.on_connection_closed)
        self.open_channel(connection)

    def on_connection_open_error(self, connection, exception):
        """ connection error callback -> reconnect

        :type connection: pika.SelectConnection
        """
        logger.error('unable to connect', exc_info=exception)

        wait_secs = self.reconnect_timeout
        logger.info('reconnecting in %d s', wait_secs)
        time.sleep(wait_secs)

        self.reconnect()

    def on_connection_closed(self, connection, exception):
        """ close connection callback -> reconnect if unexpected.

        :type connection: pika.connection.Connection
        :param Exception exception: An exception representing any errors
        """
        self._channel = None
        if self.stopped:
            connection.ioloop.stop()
        else:
            logger.warning(
                'Connection closed, reopening in 5 seconds: %s',
                exception)
            connection.ioloop.call_later(5, self.reconnect)

    def open_channel(self, connection):
        """ open a new channel.

        :type connection: pika.connection.Connection
        """
        logger.info('open_channel on connection=%r')
        connection.channel(on_open_callback=self.on_channel_open)

    def close_channel(self):
        """Call to close the channel with RabbitMQ cleanly by issuing the
        Channel.Close RPC command.

        """
        logger.info('closing the channel')
        if self._channel:
            self._channel.close()

    def on_channel_open(self, channel):
        """ channel callback -> configure channel.

        :type channel: pika.channel.Channel
        """
        logger.info('channel %i opened', channel)
        self._channel = channel
        logger.debug('adding on_close_callback, on_cancel_callback')
        channel.add_on_close_callback(self.on_channel_closed)
        channel.add_on_cancel_callback(self.on_consumer_cancelled)
        self._setup(channel, self.on_message)

    def on_channel_closed(self, channel, exception):
        """ close connection if channel gets closed.

        :type channel: pika.channel.Channel
        :param Exception exception: An exception representing any errors
        """
        logger.warning('channel %i closed: %s',
                       channel, exception)
        channel.connection.close()

    #
    # message handling
    #

    def on_consumer_cancelled(self, method_frame):
        """Invoked by pika when RabbitMQ sends a Basic.Cancel for a consumer
        receiving messages.

        :param pika.frame.Method method_frame: The Basic.Cancel frame

        """
        logger.info('Consumer was cancelled remotely, shutting down: %r',
                    method_frame)
        # TODO: can we get the channel from a Basic.Cancel frame?
        if self._channel:
            self._channel.close()

    def on_message(self, channel, method, properties, body):
        """ handle message delivery.

        :type channel: pika.channel.Channel
        :type method: pika.Spec.Basic.Deliver
        :param properties: pika.Spec.BasicProperties
        :type body: str|unicode

        """
        logger.info('Received message on channel=%d delivery_tag=%d (from %r)',
                    channel, method.delivery_tag, properties.app_id)

        try:
            self.consume(channel, method, properties, body)
        except Exception:
            logger.error("Consume on channel=%d delivery_tag=%d failed",
                         channel, method.delivery_tag, exc_info=True)

    #
    # startup/shutdown
    #

    def run(self):
        """Run the example consumer by connecting to RabbitMQ and then
        starting the IOLoop to block and allow the SelectConnection to operate.

        """
        self._connection = self.connect()
        self._connection.ioloop.start()

    def stop(self):
        """ stop the consumer

        will cause on_cancelok
        """
        logger.info('stopping')
        self.stopped = True  # avoid re-connect
        self.stop_consuming()
        self.close_channel()

        # The IOLoop is started again because this method is invoked when
        # CTRL-C is pressed raising a KeyboardInterrupt exception. This
        # exception stops the IOLoop which needs to be running for pika to
        # communicate with RabbitMQ.
        # All of the commands issued prior to starting the IOLoop will be
        # buffered but not processed.
        self._connection.ioloop.start()

        logger.info('stopped')

    def stop_consuming(self):
        """ issue a basic_cancel (to stop basic_consume). """
        if self._channel:
            logger.info('Sending a Basic.Cancel RPC command to RabbitMQ')
            for tag in self._channel.consumer_tags:
                self._channel.basic_cancel(tag, callback=self.on_cancelok)

    def on_cancelok(self, frame):
        """ close channel when broker acks the cancellation of a consumer.

        :type frame: pika.frame.Method
        :param frame: a Basic.CancelOk frame
        """
        logger.info('Cancelled consumer with tag %r',
                    frame.method.consumer_tag)


def demo_callback(channel, method, properties, body):
    """
    A basic example consumer callback.
    """
    content_type = properties.content_type or 'text/plain'
    content_encoding = properties.content_encoding or 'ascii'
    body = body.decode(content_encoding)

    # fail on some messages (depends on delivery_tag)
    if method.delivery_tag % 3 == 0:
        logger.info('Failing message (type=%r, encoding=%r, len=%d, key=%r)',
                    content_type, content_encoding, len(body),
                    method.routing_key)
        raise RuntimeError('intentional, delivery_tag % 3 == 0')

    logger.info('Acking message (type=%r, encoding=%r, len=%d, key=%r)',
                content_type, content_encoding, len(body), method.routing_key)
    channel.basic_ack(delivery_tag=method.delivery_tag)
