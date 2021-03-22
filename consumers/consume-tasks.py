#!/usr/bin/env python
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
Cerebrum task consumer.

This daemon starts an AMQP client that binds a task generators to message
broker queues.

Each item in :py:attr:`TaskHandlerConfig.tasks` contains a source and a
callback.  The source is a queue to listen to, and the callback is a function
to transform a message into an iterable of tasks:

1. We configure our broker using :py:module:`Cerebrum.modules.amqp.consumer`,
   and set up exchanges, queues and binds from the
   :py:class:`.TaskHandlerConfig`.

2. For each :py:attr:`.TaskHandlerConfig.tasks`, we set up a
   callback, which calls :py:method:`.TaskHandler.handle` with a
   :py:class:`Cerebrum.modules.amqp.handler.`Event` object.

3. This will in turn call the configured ``get_tasks(db, event)`` function from
   the config, which should return an iterable of zero or more
   :py:class:`Cerebrum.modules.tasks.task_models.Task` objects.

Any task returned by one of these transforms gets added to the internal
Cerebrum task queue _unless_ there is already a similar task queued for
processing with a shorter delay.
"""
import argparse
import logging

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.config.loader import read_config as read_config_file
from Cerebrum.database.ctx import db_context
from Cerebrum.modules.amqp.config import get_connection_params, ConsumerConfig
from Cerebrum.modules.amqp.consumer import (
    ChannelSetup,
    ChannelListeners,
    Manager
)
from Cerebrum.modules.amqp.handlers import AbstractConsumerHandler
from Cerebrum.modules.tasks.config import TaskListMixin
from Cerebrum.modules.tasks.task_queue import TaskQueue
from Cerebrum.utils.argutils import add_commit_args

logger = logging.getLogger(__name__)


class TaskHandlerConfig(ConsumerConfig, TaskListMixin):
    """ Joint consumer/task config. """

    @classmethod
    def from_file(cls, filename):
        config = cls()
        config.load_dict(read_config_file(filename))
        return config


class TaskHandler(AbstractConsumerHandler):
    """ ConsumerHandler for translating messages to tasks.  """

    def __init__(self, task_callback, db_callback, dryrun):
        """
        :param task_callback:
            A function that translates an Event into an iterable of Tasks.

        :param db_callback:
            A function that takes no arguments and returns a
            Cerebrum.database.Database object.

        :param dryrun:
            Do not commit changes to the database.
        """
        self.get_tasks = task_callback
        self.get_db = db_callback
        self.dryrun = dryrun

    def handle(self, event):
        logger.info('got event=%r on channel=%r', event, event.channel)

        with db_context(self.get_db(), self.dryrun) as db:
            queue = TaskQueue(db)
            for task in (self.get_tasks(db, event) or ()):
                logger.debug('adding task %s', repr(task))
                queue.push(task, ignore_nbf_after=True)

    def on_error(self, event, error):
        # TODO: We should also implement better error handling here.
        #       Maybe add a dead letter queue with a timeout, so that `nack`
        #       won't add messages back to _our_ queue immediately.
        ct = event.method.consumer_tag
        dt = event.method.delivery_tag
        logger.debug('abort %s/%s', ct, dt)
        event.channel.basic_nack(delivery_tag=dt)

    def reschedule(self, event, dates):
        # TODO: We should probably re-consider the design of the
        #       AbstractConsumerHandler.  The reschedule call might not be
        #       appropriate in this "interface".
        raise NotImplementedError()


def set_pika_loglevel(level=logging.INFO, force=False):
    pika_logger = logging.getLogger('pika')
    if force or pika_logger.level == logging.NOTSET:
        pika_logger.setLevel(level)


def get_consumer(config, dryrun):
    """ Create and configure an amqp consumer. """

    # connection
    connection_params = get_connection_params(config.connection)

    # channel setup
    setup = ChannelSetup(exchanges=config.exchanges,
                         queues=config.queues,
                         bindings=config.bindings,
                         flags=ChannelSetup.Flags.ALL)

    # channel consumers
    consumers = ChannelListeners(consumer_tag_prefix=config.consumer_tag)

    for task in config.tasks:
        on_message = TaskHandler(
            task_callback=task.get_tasks,
            db_callback=Factory.get('Database'),
            dryrun=dryrun,
        )
        # each task source is a queue name to listen to
        consumers.set_listener(task.source, on_message)

    return Manager(connection_params, setup, consumers)


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Consume, translate and store tasks from a broker',
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

    add_commit_args(parser.add_argument_group('Database'))
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)
    set_pika_loglevel(logging.INFO)

    logger.info("Starting %s", parser.prog)
    logger.debug("args: %r", args)

    config = TaskHandlerConfig.from_file(args.config)
    if args.show_config:
        import pprint
        pprint.pprint(config.dump_dict())
        raise SystemExit()
    config.validate()

    if not config.tasks:
        raise RuntimeError('no tasks in config - nothing to do')

    mgr = get_consumer(config, not args.commit)
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
