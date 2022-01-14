#!/usr/bin/env python
#
# -*- coding: utf-8 -*-
#
# Copyright 2021 University of Oslo, Norway
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
Generic Cerebrum task consumer.

This daemon starts an AMQP client that binds a callback to a message broker
queue.  Each message gets processed by the callback, and then acked.  This can
be useful for very simple consumers, or to test the consumer itself with a
no-op message handler.


Configuration
-------------
See py:mod:`Cerebrum.modules.amqp.config` for more details on connection and
declaration options.

Minimal example - assume that

- Our server is running unencrypted on localhost, with login guest:guest
- A queue *foo* already exists, on virtualhost /

If we want to receive and ack messages (without processing them), we can e.g.
configure the *truth* function from the *operator* module as a callback (as it
takes one value of any type as input).

Yaml-config:

::

    connection: {}
    exchanges: []
    queues: []
    bindings: []
    consumer_tag: my-test
    callbacks:
      - source: foo
        callback: "operator:truth"
"""
from __future__ import absolute_import, print_function, unicode_literals
import argparse
import logging

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.config.configuration import (
    ConfigDescriptor,
    Configuration,
    Namespace,
)
from Cerebrum.config.settings import Iterable, String
from Cerebrum.config.loader import read_config as read_config_file
from Cerebrum.modules.amqp.config import get_connection_params, ConsumerConfig
from Cerebrum.modules.amqp.consumer import (
    ChannelSetup,
    ChannelListeners,
    Manager
)
from Cerebrum.modules.amqp.handlers import AbstractConsumerHandler
from Cerebrum.utils.module import resolve

logger = logging.getLogger(__name__)


class CallbackConfig(Configuration):
    """ a single queue-to-callback mapping. """

    source = ConfigDescriptor(
        String,
        doc='queue to apply callback to',
    )

    callback = ConfigDescriptor(
        String,
        doc='callback, signature: func(event)',
    )


class CallbackHandlerConfig(ConsumerConfig):
    """ ConsumerConfig with an additional *callbacks* list. """

    callbacks = ConfigDescriptor(
        Iterable,
        template=Namespace(config=CallbackConfig),
        doc="a list of queue-to-callback mappings",
    )

    @classmethod
    def from_file(cls, filename):
        """ Load config from *filename*. """
        config = cls()
        config.load_dict(read_config_file(filename))
        return config


class CallbackHandler(AbstractConsumerHandler):
    """
    ConsumerHandler for processing messages using a *callback*.

    This class is meant to be used as a queue/channel listener with
    py:class:`Cerebrum.modules.amqp.consumer.ChannelListeners`.  Initialize
    with a callback function to process
    py:class:`Cerebrum.modules.amqp.handlers.Event` objects.  The callback
    should take one argument - the event object to process.
    """

    def __init__(self, callback):
        self._callback = callback

    def handle(self, event):
        """
        :type event: Cerebrum.modules.amqp.handlers.Event
        """
        ct = event.method.consumer_tag
        dt = event.method.delivery_tag
        logger.info('receive %s/%s (event=%s)', ct, dt, repr(event))
        self._callback(event)

    def on_ok(self, event):
        ct = event.method.consumer_tag
        dt = event.method.delivery_tag
        logger.info('confirm %s/%s', ct, dt)
        event.channel.basic_ack(delivery_tag=dt)

    def on_error(self, event, error):
        ct = event.method.consumer_tag
        dt = event.method.delivery_tag
        logger.info('abort %s/%s', ct, dt)
        event.channel.basic_nack(delivery_tag=dt)

    def reschedule(self, event, dates):
        raise NotImplementedError()


def set_pika_loglevel(level=logging.INFO, force=False):
    pika_logger = logging.getLogger('pika')
    if force or pika_logger.level == logging.NOTSET:
        pika_logger.setLevel(level)


def get_consumer(config):
    """
    Create and configure an amqp consumer.

    :rtype: Cerebrum.modules.amqp.consumer.Manager
    """
    connection_params = get_connection_params(config.connection)
    setup = ChannelSetup(
        exchanges=config.exchanges,
        queues=config.queues,
        bindings=config.bindings,
        flags=ChannelSetup.Flags.ALL,
    )

    consumers = ChannelListeners(consumer_tag_prefix=config.consumer_tag)
    for cb_config in config.callbacks:
        consumers.set_listener(
            cb_config.source,
            CallbackHandler(resolve(cb_config.callback)),
        )

    return Manager(connection_params, setup, consumers)


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Consume and process messages from a broker',
    )
    parser.add_argument(
        '--show-config',
        action='store_true',
        help='show configuration and exit',
    )
    parser.add_argument(
        '-c', '--config',
        required=True,
    )
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)
    set_pika_loglevel(logging.INFO)

    logger.info("Starting %s", parser.prog)
    logger.debug("args: %r", args)

    config = CallbackHandlerConfig.from_file(args.config)
    if args.show_config:
        import pprint
        pprint.pprint(config.dump_dict())
        raise SystemExit()

    config.validate()
    if not config.callbacks:
        raise RuntimeError('no callbacks in config - nothing to do')

    mgr = get_consumer(config)
    try:
        mgr.run()
    except KeyboardInterrupt:
        logger.info('Stopping (KeyboardInterrupt)')
    except Exception:
        logger.error('Stopping (unhandled exception)')
        raise
    finally:
        mgr.stop()


if __name__ == '__main__':
    main()
