#!/usr/bin/env python
# -*- encoding: utf-8 -*-
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
""" Event handler for Exchange provisioning (Cerebrum.modules.exchange).

Once started, this dæmon will listen for changes in the Cerebrum database, and
attempt to update Exchange with the appropriate changes.

This process accepts the following signals:

SIGHUP (any process):
    Gracefully stop the utils.

SIGUSR1 (main process)
    List current processes, pids and their state.
"""
import argparse

from multiprocessing import Queue

from Cerebrum import Utils
from Cerebrum.modules.event import utils
from Cerebrum.modules.event import evhandlers
from Cerebrum.modules.no.uio.exchange.consumer import ExchangeEventHandler
from Cerebrum.modules.exchange.config import load_config


TARGET_SYSTEM = 'Exchange'


class Manager(utils.Manager):
    pass
# Inject Queue implementations:
Manager.register('queue', Queue)
Manager.register('log_queue', Queue)


def serve(logger, config, num_workers, enable_listener,
          enable_collectors):
    logger.info('Starting {!r} event utils'.format(TARGET_SYSTEM))

    channels = [TARGET_SYSTEM, ]
    exchanged = utils.ProcessHandler(logger=logger, manager=Manager)

    event_queue = exchanged.mgr.queue()

    Handler = getattr(Utils.dyn_import(config.handler.handler_mod),
                      config.handler.handler_class)

    for i in range(0, num_workers):
        exchanged.add_process(
            Handler,
            queue=event_queue,
            log_queue=exchanged.log_queue,
            running=exchanged.run_trigger,
            config=config)

    if enable_listener:
        exchanged.add_process(
            evhandlers.DBEventListener,
            queue=event_queue,
            log_queue=exchanged.log_queue,
            running=exchanged.run_trigger,
            channels=channels)

    if enable_collectors:
        for chan in channels:
            exchanged.add_process(
                evhandlers.DBEventCollector,
                queue=event_queue,
                log_queue=exchanged.log_queue,
                running=exchanged.run_trigger,
                channel=chan,
                config=config.eventcollector)

    exchanged.serve()


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

    # TODO: Make option for this?
    # Update `event_to_target` mapping tables
    utils.update_system_mappings(
        parser.prog, TARGET_SYSTEM, ExchangeEventHandler.event_map.events)

    args = parser.parse_args(args)
    config = load_config(filepath=args.configfile)

    # Run event processes
    serve(
        logger,
        config,
        int(args.num_workers),
        args.listen_db,
        args.collect_db)


if __name__ == '__main__':
    main()
