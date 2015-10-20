#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2014 University of Oslo, Norway
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
"""Event-daemon used for pushing updates to systems"""

import eventconf

import getopt
import multiprocessing
from multiprocessing import managers
import Queue
import threading

import sys
import signal
import ctypes

from Cerebrum import Utils
from Cerebrum.modules.event.NotificationCollector import NotificationCollector
from Cerebrum.modules.event.DelayedNotificationCollector import (
    DelayedNotificationCollector)


logger = Utils.Factory.get_logger('cronjob')


def usage(i=0):
    print('usage: python event_daemon.py [--type --no-notifications '
          '--no-delayed-notifications]')
    print('-n --no-notifications            Disable the NotificationCollector')
    print('-d --no-delayed-notifications    '
          'Disable the DelayedNotificationCollector')
    print('-h --help                        This help')
    print('')
    print('HUP me ONCE (but not my children) if you want to shut me down'
          'with grace.')
    sys.exit(i)


# Logger function that runs in it's own thread. We need to do it like this,
# since the logger is not process safe
def log_it(queue, run_state):
    logger.info('Started logging thread')
    # TODO: This is highly incorrect. We should be sure the queue is empty
    # before quitting. Call join or something on the processes that logs or
    # something
    run = run_state.value
    while run:
        try:
            entry = queue.get(block=True, timeout=5)
        except Queue.Empty:
            run = run_state.value
            continue
        log_func = logger.__getattribute__(entry[0])
        log_func(*entry[1])
    logger.info('Shutting down logger thread')


def signal_hup_handler(signal, frame):
    frame.f_locals['run_state'].value = 0


def main():
    log_queue = multiprocessing.Queue()
    # Shared varaiable, used to tell the children to shut down
    run_state = multiprocessing.Value(ctypes.c_int, 1)
    # Separate run-state for the logger
    logger_run_state = multiprocessing.Value(ctypes.c_int, 1)

    # Parse args
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   't:ndmh',
                                   ['type=',
                                    'no-notifications',
                                    'no-delayed-notifications',
                                    'mock',
                                    'help'])
    except getopt.GetoptError, err:
        print err
        usage(1)

    conf = None
    notifications = True
    delayed_notifications = True
    mock = False

    for opt, val in opts:
        if opt in ('-t', '--type'):
            conf = eventconf.CONFIG[val]
            # TODO: Verify config here?
        elif opt in ('-n', '--no-notifications'):
            notifications = False
        elif opt in ('-d', '--no-delayed-notifications'):
            delayed_notifications = False
        elif opt in ('-m', '--mock'):
            mock = True
        elif opt in ('-h', '--help'):
            usage(0)

    # Can't run without a config!
    if not conf:
        logger.error('No configuration given')
        run_state.value = 0
        usage(2)

    # Start the thread that writes to the log
    logger_thread = threading.Thread(target=log_it,
                                     args=(log_queue, logger_run_state,))
    logger_thread.start()

    # We need to store the procecess
    procs = []

    # Helper for importing correct classes dynamically
    # TODO: Should this be done in a prettier way?
    def dyn_import(class_name):
        return getattr(Utils.dyn_import(class_name),
                       class_name.split('.')[-1])

    # Import the event handeler we need to use
    event_handler_class = dyn_import(conf['event_handler_class'])
    logger.debug("Event_handler_class: %s", event_handler_class)

    # Define the queue of events to be processed.
    # We look for classes that we can import dynamically, but if that is not
    # defined, we fall back to the BaseQueue-class, which really is
    # multiprocessing.Queue (as of now).
    # TODO: This is not totally sane? Should we support mixins? We should
    # define a manager in BaseQueue, and implement everything on top of that?
    try:
        event_queue_class_name = conf['event_queue_class']
    except KeyError:
        event_queue_class_name = 'Cerebrum.modules.event.BaseQueue'

    class QueueManager(managers.BaseManager):
        pass

    QueueManager.register(event_queue_class_name,
                          dyn_import(event_queue_class_name))
    q_manager = QueueManager()
    q_manager.start()
    event_queue = getattr(q_manager, event_queue_class_name)()

    # Create all the event-handeler processes
    for i in range(0, conf['concurrent_workers']):
        procs.append(event_handler_class(conf, event_queue, log_queue,
                                         run_state, mock))

    # Create the NotificationCollector if appropriate
    if notifications:
        nc = NotificationCollector(event_queue,
                                   conf['event_channels'],
                                   log_queue,
                                   run_state)

    # Create the DelayedNotificationCollector if appropriate
    if delayed_notifications:
        dnc = DelayedNotificationCollector(event_queue,
                                           conf,
                                           log_queue,
                                           run_state)

    # Start all processes
    for x in procs:
        x.daemon = True
        x.start()

    # Start the NotificationCollector
    if notifications:
        nc.daemon = True
        nc.start()
        procs.append(nc)

    # Start the DelayedNotificationCollector
    if delayed_notifications:
        dnc.daemon = True
        dnc.start()
        procs.append(dnc)

    # Trap the Hangup-signal, we use this in order to shut down nicely
    signal.signal(signal.SIGHUP, signal_hup_handler)
    signal.pause()

    for x in procs:
        x.join()

    q_manager.shutdown()

    # Stop the logger
    logger_run_state.value = 0
    logger_thread.join()

    # TODO: Instead of signal.pause, wait for joinage of proccesses or
    # something

    # TODO: Here
    # - Trap singals. We want to exit cleanly <- Done to some extent.
    #     Verify furter

if __name__ == '__main__':
    main()
