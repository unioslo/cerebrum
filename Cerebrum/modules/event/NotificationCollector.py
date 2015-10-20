#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2015 University of Oslo, Norway
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
from Cerebrum.Utils import read_password, Factory
from Cerebrum.modules.event.HackedLogger import Logger

import time
import multiprocessing

import select
import psycopg2
import psycopg2.extensions
from psycopg2 import OperationalError


class NotificationCollector(multiprocessing.Process):
    def __init__(self, event_queue, channels, logger_queue, run_state):
        """
        NotificationCollector initzialization.

        @type event_queue: multiprocessing.Queue
        @param event_queue: The queue that events get queued on

        @type channels: list
        @param channels: A list of channel names that should be listened on

        @type logger_queue: multiprocessing.Queue
        @param logger_queue: The queue used for logging.

        @type run_state: multiprocessing.Value(ctypes.c_int)
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
                 cereconf.CEREBRUM_DATABASE_CONNECT_DATA['host'])}

        self.event_queue = event_queue
        self.run_state = run_state
        self.channels = channels

        # TODO: This is a hack. Fix it
        self.logger_queue = logger_queue
        self.logger = Logger(self.logger_queue)

        super(NotificationCollector, self).__init__()

    # TODO: Move 'channels' into self? Lookup from DB?
    def _connect_db(self, channels):
        """Utility function used to connect to the database

        @type channels: list
        @param channels: A list of channel names to listen on
        """
        # Initzialize DB
        self.db = Factory.get('Database')(client_encoding='UTF-8')

        # Initzialize connection for listening
        self.conn = psycopg2.connect(self.DSN)
        self.conn.set_isolation_level(
            psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT
        )

        self.curs = self.conn.cursor()
        for x in channels:
            # It is important to put the channel name in quotation marks. If we
            # don't do that, the channel name gets case folded.
            # (http://www.postgresql.org/message-id/AANLkTi=qi0DXZcDoMy5hHJQG \
            #        JP5upJPsGKVt+ySh5tmS@mail.gmail.com)
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
                    self.logger.info(
                        'NotificationCollecor connected to database')
                except OperationalError:
                    self.logger.warn(
                        'OperationalError occured, failed reconnection to '
                        'database')
                    time.sleep(5)
                    continue

            # Wait for something to happen on the connection
            if select.select([self.conn], [], [], 5) == ([], [], []):
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
                        'OperationalError occured, lost connection '
                        'to database')
                    connected = False
                    time.sleep(5)

                # Put all notifications in the queue
                while self.conn.notifies:
                    # Pop the first item of the list, since we want a FIFO
                    # queue, not a LIFO.
                    notification = self.conn.notifies.pop(0)
                    # Extract channel and the event
                    # Dictifying the event in order to pickle it when
                    # enqueueuing.
                    ev = self.db.get_event(int(notification.payload))
                    cp = {'channel': notification.channel,
                          'event': dict(ev)}
                    # Append the channel and payload to the queue
                    self.event_queue.put(cp)
                    self.logger.debug2('NC enqueueing %s' % str(notification))
                # Rolling back to avoid IDLE in transact
                self.db.rollback()
        self.logger.info('NotificationCollector stopped')
