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
"""Collector of notify-events from postgresql"""

import cereconf
from Cerebrum.Utils import read_password

import time
import processing

import select
import psycopg2
import psycopg2.extensions
from psycopg2 import OperationalError


class NotificationCollector(processing.Process):
    def __init__(self, event_queue, channels, logger, run_state):
        """
        NotificationCollector initzialization.

        @type event_queue: processing.Queue
        @param event_queue: The queue that events get queued on
        
        @type channels: list
        @param channels: A list of channel names that should be listened on

        @type logger: Cerebrum.modules.cerelog.CerebrumLogger
        @param logger: The logger used for logging

        @type run_state: processing.Value(ctypes.c_int)
        @param run_state: A shared object used to determine if we should
            stop execution or not
        """

        dsn_fmt = 'dbname=%(db)s user=%(usr)s password=%(pass)s host=%(host)s'
        self.DSN = dsn_fmt % \
                {'db': cereconf.CEREBRUM_DATABASE_NAME,
                 'usr': cereconf.CEREBRUM_DATABASE_CONNECT_DATA['user'],
                 'host': cereconf.CEREBRUM_DATABASE_CONNECT_DATA['host'],
                 'pass': read_password(
                            cereconf.CEREBRUM_DATABASE_CONNECT_DATA['user'],
                            cereconf.CEREBRUM_DATABASE_NAME,
                            cereconf.CEREBRUM_DATABASE_CONNECT_DATA['host']
                         )
                }
        
        self.event_queue = event_queue
        self.logger = logger
        self.run_state = run_state
        self.channels = channels

        super(NotificationCollector, self).__init__()

    # TODO: Move 'channels' into self? Lookup from DB?
    def _connect_db(self, channels):
        """Utility function used to connect to the database

        @type channels: list
        @param channels: A list of channel names to listen on
        """
        self.conn = psycopg2.connect(self.DSN)
        self.conn.set_isolation_level(
                psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT
        )

        self.curs = self.conn.cursor()
        for x in channels:
            # It is important to put the channel name in quotation marks. If we
            # don't do that, the channel name gets case folded.
            # (http://www.postgresql.org/message-id/AANLkTi=qi0DXZcDoMy5hHJQGJ \
            #        P5upJPsGKVt+ySh5tmS@mail.gmail.com)
            self.curs.execute('LISTEN "%s";' % x)

    def run(self):
        """
        Gets called by processin.Process.__init__.
        Main loop of process.
        """
        self.logger.debug2('NotificationCollector running')

        connected = False
        # This is a tiny bit ugly, but it works. To make it pretty
        # complicates a lot. A prettier way could be to use a manager,
        # and pass in a python type..
        while self.run_state.value:
            if not connected:
                try:
                    self._connect_db(self.channels)
                    connected = True
                    self.logger.info("NotificationCollecor connected to database")
                except OperationalError:
                    self.logger.warn(
                    'OperationalError occured, failed reconnection to database')
                    time.sleep(5)
                    continue

            # Wait for something to happen on the connection
            if select.select([self.conn],[],[],5) == ([],[],[]):
                pass
            else:
                # Something has indeed happende. Poll the connection. If
                # the connection is down (OperationalError), we reconnect
                # and resume operation.
                try:
                    self.conn.poll()
                except OperationalError:
                    # If we get an operational error, the connection is broken.
                    # We set connected to fals, this results in indefinate
                    # reconnection attempts.
                    self.logger.warn(
                        'OperationalError occured, lost connection to database')
                    connected = False
                    time.sleep(5)

                # Put all notifications in the queue
                # We reverse it, since we want FIFO, not LIFO.
                while reversed(self.conn.notifies):
                    notification = self.conn.notifies.pop()
                    # Extract channel and payload
                    cp = {'channel': notification.channel,
                          'payload': int(notification.payload)}
                    # Append the channel and payload to the queue
                    self.event_queue.put(cp)
                    self.logger.debug2('NC enqueueing %s' % str(notification))
        self.logger.info('NotificationCollector stopped')
