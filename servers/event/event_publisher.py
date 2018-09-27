#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2017-2018 University of Oslo, Norway
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
""" Event handler for publishing SCIM-messages to the Message Queue.

Once started, this daemon will listen for changes in the Cerebrum database, and
attempt to publish SCIM-formatted messages using some MQ publisher.

This process accepts the following signals:

SIGHUP (any process):
    Gracefully stop the utils.

SIGUSR1 (main process)
    List current processes, pids and their state.
"""
import argparse
import logging
from multiprocessing import Queue

import Cerebrum.logutils
from Cerebrum import Utils
from Cerebrum.modules.event import utils
from Cerebrum.modules.event_publisher import consumer
from Cerebrum.modules.event_publisher.config import load_daemon_config
from Cerebrum.utils.pidcontext import Pid

logger = logging.getLogger(__name__)


class Manager(utils.Manager):
    pass


# Inject our queue implementation:
# TODO: This should probably be a Queue.Queue, since it's handled by a Manager!
Manager.register('queue', Queue)


def unlock_all_events():
    from Cerebrum.Utils import Factory
    from Cerebrum.modules.event_publisher.eventdb import EventsAccessor
    database = Factory.get('Database')()
    EventsAccessor(database).release_all()
    database.commit()


def serve(config, num_workers, enable_listener, enable_collector):

    # Generic event processing daemon
    daemon = utils.ProcessHandler(manager=Manager)

    event_queue = daemon.mgr.queue()

    # The 'event handler'
    # Listens on the `event_queue` and processes events that are pushed onto it
    for i in range(0, num_workers):
        daemon.add_process(
            consumer.EventConsumer,
            config.event_publisher,
            config.event_formatter,
            queue=event_queue,
            log_queue=daemon.log_queue,
            running=daemon.run_trigger,
        )

    # The 'event listener'
    # Listens to 'events' from the database, fetches related event records, and
    # pushes events onto the `event_queue`.
    if enable_listener:
        daemon.add_process(
            consumer.EventListener,
            queue=event_queue,
            log_queue=daemon.log_queue,
            running=daemon.run_trigger)

    # The 'event collector'
    # Regularly pulls event records from the database, and pushes events onto
    # the `event_queue`.
    if enable_collector:
        daemon.add_process(
            consumer.EventCollector,
            queue=event_queue,
            log_queue=daemon.log_queue,
            running=daemon.run_trigger,
            config=config.event_daemon_collector)

    daemon.serve()


def show_config(config):
    import pprint
    pprint.pprint(config.dump_dict())


def main(args=None):
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument('-c', '--config',
                        dest='configfile',
                        metavar='FILE',
                        default=None,
                        help='Use a custom configuration file')

    parser.add_argument('--show-config',
                        dest='show_config',
                        action='store_true',
                        default=False,
                        help='Show config and exit')

    parser.add_argument('-n', '--num-workers',
                        dest='num_workers',
                        metavar='NUM',
                        default=1,
                        help=('Use %(metavar)s processes to handle incoming'
                              ' events (default=%(default)s)'))

    parser.add_argument('--no-listener',
                        dest='listen_db',
                        action='store_false',
                        default=True,
                        help='Disable event listener')

    parser.add_argument('--no-collection',
                        dest='collect_db',
                        action='store_false',
                        default=True,
                        help='Disable event collectors')

    parser.add_argument('--unlock-events',
                        dest='unlock_events',
                        action='store_true',
                        default=False,
                        help='Unlock events that remain locked from '
                             'previous runs')

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(args)
    Cerebrum.logutils.autoconf(__name__, args)

    config = load_daemon_config(filepath=args.configfile)

    if args.show_config:
        show_config(config)
        raise SystemExit()

    # Run event processes
    logger.info('Starting publisher event utils')
    with Pid():
        if args.unlock_events:
            unlock_all_events()
        serve(
            config,
            int(args.num_workers),
            args.listen_db,
            args.collect_db)

    logger.info('Event publisher stopped')


if __name__ == '__main__':
    main()
