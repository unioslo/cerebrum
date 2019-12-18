#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2015-2018 University of Oslo, Norway
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
""" Event handler for Exchange provisioning (Cerebrum.modules.exchange).

Once started, this dæmon will listen for changes in the Cerebrum database, and
attempt to update Exchange with the appropriate changes.

This process accepts the following signals:

SIGHUP (any process):
    Gracefully stop the utils.

SIGUSR1 (main process)
    List current processes, pids and their state.
"""

from __future__ import unicode_literals

import argparse

from six.moves.queue import Queue

from Cerebrum import Utils
from Cerebrum.modules.event import utils
from Cerebrum.modules.event import evhandlers
from Cerebrum.modules.exchange.config import load_config


TARGET_SYSTEM = 'Exchange'


class Manager(utils.Manager):
    pass


# Inject our queue implementation:
Manager.register(str('queue'), Queue)


def serve(config, num_workers, enable_listener, enable_collectors):
    channels = [TARGET_SYSTEM, ]
    exchanged = utils.ProcessHandler(manager=Manager)

    event_queue = exchanged.mgr.queue(maxsize=1000)
    queues = []

    Handler = getattr(Utils.dyn_import(config.handler.handler_mod),
                      config.handler.handler_class)

    for i in range(0, num_workers):
        exchanged.add_process(
            Handler(
                daemon=True,
                queue=event_queue,
                log_channel=exchanged.log_channel,
                running=exchanged.run_trigger,
                config=config,
                mock=config.client.mock))

    if (config.deferred_handler.handler_mod and
            config.deferred_handler.handler_class):
        group_event_queue = exchanged.mgr.queue()
        hand = getattr(Utils.dyn_import(config.deferred_handler.handler_mod),
                       config.deferred_handler.handler_class)
        exchanged.add_process(
            hand(
                daemon=True,
                queue=group_event_queue,
                log_channel=exchanged.log_channel,
                running=exchanged.run_trigger,
                config=config,
                mock=config.client.mock))
        queues.append(group_event_queue)

    if enable_listener:
        exchanged.add_process(
            evhandlers.EventLogListener(
                daemon=True,
                queue=event_queue,
                fan_out_queues=queues,
                log_channel=exchanged.log_channel,
                running=exchanged.run_trigger,
                channels=channels))

    if enable_collectors:
        for chan in channels:
            exchanged.add_process(
                evhandlers.EventLogCollector(
                    daemon=True,
                    queue=event_queue,
                    fan_out_queues=queues,
                    log_channel=exchanged.log_channel,
                    running=exchanged.run_trigger,
                    channel=chan,
                    config=config.eventcollector))

    exchanged.serve()


def update_mappings(progname, config):
    events = getattr(Utils.dyn_import(config.handler.handler_mod),
                     config.handler.handler_class).event_map.events

    if (config.deferred_handler.handler_mod and
            config.deferred_handler.handler_class):
        events.extend(getattr(Utils.dyn_import(
            config.deferred_handler.handler_mod),
            config.deferred_handler.handler_class).event_map.events)

    utils.update_system_mappings(
        progname, TARGET_SYSTEM, events)


def main(args=None):
    logger = Utils.Factory.get_logger('cronjob')
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument('-c', '--config',
                        dest='configfile',
                        metavar='FILE',
                        default=None,
                        help='Use a custom configuration file')

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

    args = parser.parse_args(args)
    config = load_config(filepath=args.configfile)

    update_mappings(parser.prog, config)

    # Run event processes
    logger.info('Starting %r event utils', TARGET_SYSTEM)
    serve(
        config,
        int(args.num_workers),
        args.listen_db,
        args.collect_db)


if __name__ == '__main__':
    main()
