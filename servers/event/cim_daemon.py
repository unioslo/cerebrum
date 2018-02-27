#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015 University of Oslo, Norway
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
""" Event utils for CIM (Cerebrum.modules.cim).

Once started, this utils will listen for changes in the Cerebrum database, and
attempt to update CIM with the same data.

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
from Cerebrum.modules.cim.consumer import CimConsumer
from Cerebrum.modules.cim.config import load_config


TARGET_SYSTEM = 'CIM'


class Manager(utils.Manager):
    pass
# Inject Queue implementations:
Manager.register('queue', Queue)
Manager.register('log_queue', Queue)


def serve(logger, cim_config, num_workers, enable_listener, enable_collectors):
    logger.info('Starting {!r} event utils'.format(TARGET_SYSTEM))

    channels = [TARGET_SYSTEM, ]
    cimd = utils.ProcessHandler(manager=Manager)

    event_queue = cimd.mgr.queue()

    for i in range(0, num_workers):
        cimd.add_process(
            CimConsumer,
            queue=event_queue,
            log_queue=cimd.log_queue,
            running=cimd.run_trigger,
            cim_config=cim_config)

    if enable_listener:
        cimd.add_process(
            evhandlers.EventLogListener,
            queue=event_queue,
            log_queue=cimd.log_queue,
            running=cimd.run_trigger,
            channels=channels)

    if enable_collectors:
        for chan in channels:
            cimd.add_process(
                evhandlers.EventLogCollector,
                queue=event_queue,
                log_queue=cimd.log_queue,
                running=cimd.run_trigger,
                channel=chan,
                config=cim_config.eventcollector)

    cimd.serve()


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
                        help=(u'Use %(metavar)s processes to handle incoming'
                              u' events (default=%(default)s)'))

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
        parser.prog, TARGET_SYSTEM, CimConsumer.event_map.events)

    args = parser.parse_args(args)
    cim_config = load_config(filepath=args.configfile)

    # Run event processes
    serve(
        logger,
        cim_config,
        int(args.num_workers),
        args.listen_db,
        args.collect_db)


if __name__ == '__main__':
    main()
