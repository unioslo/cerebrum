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
"""DelayedNotificationCollector, queues events that have not been processed,
either due to the Event Dæmon having been turned off, or if events could
somehow dissapear from the regular path taken.."""

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.modules.event.HackedLogger import Logger

import multiprocessing
import time

class DelayedNotificationCollector(multiprocessing.Process):
    def __init__(self, event_queue, config, logger_queue, run_state):
        """
        DelayedNotificationCollector initzialization. This class
        implements functionality for stuffing old events into the
        event_queue.
        
        @type event_queue: multiprocessing.Queue
        @param event_queue: The queue that events get queued on

        @type config: dict
        @param config: Dict containing configuration parameters

        @type logger_queue: multiprocessing.Queue
        @param logger_queue: The queue used for logging

        @type run_state: multiprocessing.Value(ctypes.c_int)
        @param run_state: A shared object used to determine if we should
            stop execution or not
        """
        self.event_queue = event_queue
        
        # TODO: This is a hack. Fix it
        self.logger_queue = logger_queue
        self.logger = Logger(self.logger_queue)
        
        self.run_state = run_state
        self.target_system = config['target_system']
        self.run_interval = config['run_interval']
        self.failed_limit = config['fail_limit']
        self.failed_delay = config['failed_delay']
        self.unpropagated_delay = config['unpropagated_delay']

        super(DelayedNotificationCollector, self).__init__()

    def _post_fork_init(self): 
        """Post-fork init method.

        We need to initialize the database-connection after we fork,
        or else we will get random errors since all the threads share
        the same sockets.. This is somewhat documented here:
        http://www.postgresql.org/docs/current/static/libpq-connect.html \
                #LIBPQ-CONNECT
        """
        self.db = Factory.get('Database')(client_encoding='UTF-8')
        self.co = Factory.get('Constants')(self.db)

        # Cache the int
        int(self.co.TargetSystem(self.target_system))
        self.target_system = self.co.TargetSystem(self.target_system)
        self.db.rollback()

    def run(self):
        """Main event-fetching loop. This is spawned by
        multiprocessing.Process.__init__"""
        # Do post-initialization
        self._post_fork_init()
        
        self.logger.info('DelayedNotificationCollector started')
        
        # We run until the parent gets a HUP
        while self.run_state.value:
            # Fetch old events
            # We create a new database object each time, in order to
            # clear the cache
            tmp_db = Factory.get('Database')(client_encoding='UTF-8')
            for x in tmp_db.get_unprocessed_events(self.target_system,
                                                    self.failed_limit,
                                                    self.failed_delay,
                                                    self.unpropagated_delay,
                                                    include_taken=True):
                # TODO: Should we remove channel alltogether?
                # TODO: Add support for different failed_delay on different
                #       event types?
                # Enqueue events. We must dictify the DBrow since it can't
                # be pickled.
                ev = {'channel': str(self.target_system),
                      'event': dict(x)}
                # Append the channel and payload to the queue
                self.event_queue.put(ev)
                self.logger.debug2('DNC enqueued %d' % x['event_id'])
            tmp_db.close()
        
            # Sleep for a while
            time.sleep(self.run_interval)
        self.logger.info('DelayedNotificationCollector stopped')
        

