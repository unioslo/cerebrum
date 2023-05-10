#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2017-2023 University of Oslo, Norway
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
Event handler for publishing SCIM-messages to the Message Queue.

Once started, this daemon will listen for changes in the Cerebrum database, and
attempt to publish SCIM-formatted messages using some MQ publisher.

This process accepts the following signals:

SIGHUP (any subprocess):
    Gracefully stop the service.

SIGUSR1 (main process)
    List current processes, pids and their state.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import logging

from six.moves.queue import Queue

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.modules.event import utils
from Cerebrum.modules.event_publisher import consumer
from Cerebrum.modules.event_publisher.config import load_daemon_config
from Cerebrum.utils.pidcontext import Pid

logger = logging.getLogger(__name__)


class Manager(utils.Manager):
    pass


# Inject our queue implementation:
# manager names must be bytestrings in PY2
Manager.register(str('queue'), Queue)


def unlock_all_events():
    from Cerebrum.Utils import Factory
    from Cerebrum.modules.event_publisher.eventdb import EventsAccessor
    database = Factory.get('Database')()
    EventsAccessor(database).release_all()
    database.commit()


def serve(config, num_workers, enable_listener, enable_collector):

    # Generic event processing daemon
    daemon = utils.ProcessHandler(manager=Manager)

    # The event queue must have a maxsize. If it does not, the queue will grow
    # infinitely until there is no more memory left on the machine. This
    # happens if there are many events to be processed in the database, and the
    # events are not published fast enough. Add more workers if the publishing
    # is too slow
    event_queue = daemon.mgr.queue(maxsize=1000)

    # The 'event handler'
    # Listens on the `event_queue` and processes events that are pushed onto it
    for i in range(0, num_workers):
        daemon.add_process(
            consumer.EventConsumer(
                config.event_publisher,
                config.event_formatter,
                daemon=True,
                queue=event_queue,
                log_channel=daemon.log_channel,
                running=daemon.run_trigger))

    # The 'event listener'
    # Listens to 'events' from the database, fetches related event records, and
    # pushes events onto the `event_queue`.
    if enable_listener:
        daemon.add_process(
            consumer.EventListener(
                daemon=True,
                queue=event_queue,
                log_channel=daemon.log_channel,
                running=daemon.run_trigger))

    # The 'event collector'
    # Regularly pulls event records from the database, and pushes events onto
    # the `event_queue`.
    if enable_collector:
        daemon.add_process(
            consumer.EventCollector(
                daemon=True,
                queue=event_queue,
                log_channel=daemon.log_channel,
                running=daemon.run_trigger,
                config=config.event_daemon_collector))

    daemon.serve()


def show_config(config):
    import pprint
    pprint.pprint(config.dump_dict())


def main(args=None):
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        '-c', '--config',
        default=None,
        dest='configfile',
        help='Use a custom configuration file',
        metavar='FILE',
    )
    parser.add_argument(
        '--show-config',
        action='store_true',
        default=False,
        dest='show_config',
        help='Show config and exit',
    )
    parser.add_argument(
        '-n', '--num-workers',
        default=1,
        dest='num_workers',
        help=('Use %(metavar)s processes to handle incoming'
              ' events (default=%(default)s)'),
        metavar='NUM',
    )
    parser.add_argument(
        '--no-listener',
        action='store_false',
        default=True,
        dest='listen_db',
        help='Disable event listener',
    )
    parser.add_argument(
        '--no-collection',
        action='store_false',
        default=True,
        dest='collect_db',
        help='Disable event collectors',
    )
    parser.add_argument(
        '--unlock-events',
        action='store_true',
        default=False,
        dest='unlock_events',
        help=('Unlock events that remain locked from'
              ' previous runs'),
    )

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(args)
    Cerebrum.logutils.autoconf("cronjob", args)

    config = load_daemon_config(filepath=args.configfile)

    if args.show_config:
        show_config(config)
        raise SystemExit()

    # Run event processes
    logger.info("Starting publisher event utils")
    with Pid():
        if args.unlock_events:
            unlock_all_events()
        serve(
            config,
            int(args.num_workers),
            args.listen_db,
            args.collect_db)

    logger.info("Event publisher stopped")


if __name__ == "__main__":
    main()
