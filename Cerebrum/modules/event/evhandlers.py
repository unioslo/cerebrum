#!/usr/bin/env python
# -*- encoding: utf-8 -*-
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
u""" Processes to handle events from the Cerebrum.modules.EventLog module. """

import time
import select
import traceback
from collections import namedtuple

from Cerebrum import Errors
from Cerebrum.Utils import Factory

from .EventExceptions import EventExecutionException
from .EventExceptions import EventHandlerNotImplemented

from .processes import ProcessLoggingMixin
from .processes import ProcessLoopMixin
from .processes import ProcessDBMixin
from .processes import ProcessQueueMixin
from .processes import QueueListener


EventItem = namedtuple('EventItem', ('channel', 'event'))
u""" Simple event representation for the queue. """


class EventConsumer(
        ProcessDBMixin,
        ProcessLoggingMixin,
        QueueListener):
    u""" Simple class to handle Cerebrum.modules.EventLog events.

    This process takes events from a queue, and processes it:

      1. Lock the event from other EventConsumers
      2. Handle the event (`handle_event`)
      3. Report event state back to the DB

    The actual event handling is abstract (`handle_event`), and should be
    implemented in subclasses.

    """

    def handle(self, item):
        u""" Event processing.

        :param EventItem item:
            A named tuple with two items:
              'channel' (str): The channel that the event was received on.
              'event' (dict): Event data returned from `eventlog.get_event()`

        """
        if not isinstance(item, EventItem):
            self.logger.error(u'Unknown event type: {!r}: {!r}',
                              type(item), item)
            return
        ch = item.channel
        ev = item.event
        self.logger.debug2(u'Got a new event on channel {!r}: {!r}', ch, ev)

        try:
            # Acquire lock.
            # We must commit here, regardless of dryrun?
            self.db.lock_event(ev['event_id'])
            self.db.commit()
        except Errors.NotFoundError:
            # The event was processed before we could acquire lock.
            self.logger.debug2(u'Event already processed!')
            self.db.rollback()
            return

        try:
            self.handle_event(ev)
            try:
                self.db.remove_event(ev['event_id'])
            except Errors.NotFoundError:
                self.logger.warn(u'Event deleted after lock was acquired!')
                self.db.commit()
                return

            # TODO: Store the receipt in ChangeLog! We need to handle
            # EntityTypeError and UnrelatedEvent in a appropriate manner
            # for this to work. Now we always store the reciept in the
            # functions called. That is a tad innapropriate, but also
            # correct. Hard choices.
            self.db.commit()

        except EventExecutionException as e:
            # If an event fails, we just release it, and let the
            # DelayedNotificationCollector enqueue it when appropriate
            self.logger.debug(u'Failed to process event_id {:d}: {!s}',
                              ev['event_id'], str(e))
            try:
                self.db.release_event(ev['event_id'])
            except Errors.NotFoundError:
                self.db.rollback()
            else:
                self.db.commit()

        except EventHandlerNotImplemented as e:
            self.logger.debug3('Unable to handle event_id {:d}: {!s}',
                               ev['event_id'], str(e))
            self.db.remove_event(ev['event_id'])
            self.db.commit()

        except Exception as e:
            # What happened here? We have an unhandled error,
            # which is bad. Log it!
            #
            # We don't release the "lock" on the event, since the event
            # will probably fail the next time around. Manual intervention
            # is therefore REQUIRED!
            tb = traceback.format_exc()
            tb = '\t' + tb.replace('\n', '\t\n')
            self.logger.error(u"Unhandled error!\n{!s}\n{!s}", ev, tb)

    def get_event_code(self, event):
        u""" Get a ChangeType from the event.

        :param dict event:
            The event.

        :return ChangeType:
            Returns the ChangeType code referred to in the event['event_type'].
        """
        try:
            return self.co.ChangeType(int(event['event_type']))
        except KeyError as e:
            self.logger.warn(u'Invalid event format for {!r}: {!s}', event, e)
        except Exception as e:
            self.logger.warn(u'Unable to process event {!r}: {!s}', event, e)
        return None

    def handle_event(self, event):
        u""" Call the appropriate handlers.

        :param event:
            The event to process.
        """
        key = self.get_event_code(event)
        if not key:
            return
        self.logger.debug3(u'Got event key {!r}', str(key))

        raise EventHandlerNotImplemented(
            u'Abstract event handler called')


class DBEventListener(
        ProcessQueueMixin,
        ProcessDBMixin,
        ProcessLoopMixin,
        ProcessLoggingMixin):
    u""" Producer for EventConsumer processes.

    This process LISTENs for Postgres notifications. When a notification is
    pushed, this process will fetch the actual events and push them onto a
    shared queue.

    """

    def __init__(self, channels=[], **kwargs):
        u""" Sets up listening channels.

        :param list channels:
            A list of channels to subscribe to
        """
        self.channels = channels
        super(DBEventListener, self).__init__(**kwargs)

    @property
    def subscribed(self):
        u""" Subscription status. """
        if not hasattr(self, '_subscribed'):
            self._subscribed = False
        return self._subscribed

    @subscribed.setter
    def subscribed(self, value):
        self._subscribed = bool(value)

    def subscribe(self, channels):
        u""" Subscribe to channels. """
        if not self._started:
            self.logger.warn(u'Unable to subscribe: Process not started yet')
        import psycopg2
        try:
            db = Factory.get('Database')(client_encoding=self.db_enc)
            assert psycopg2 is getattr(db, '_db_mod')
            self._conn = db._db
            self._conn.set_isolation_level(
                psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

            curs = self._conn.cursor()
            for x in channels:
                # It is important to put the channel name in quotation marks.
                # If we don't do that, the channel name gets case folded:
                #     http://www.postgresql.org/message-id/
                #     AANLkTi=qi0DXZcDoMy5hHJQGJP5upJPsGKVt+ySh5tmS@mail.gmail.co
                curs.execute('LISTEN "{!s}";'.format(x))
            self.subscribed = True
        except (psycopg2.OperationalError, RuntimeError) as e:
            self.logger.warn(u'Unable to subscribe: {!s}', str(e))
        except Exception as e:
            self.logger.error(u'Unknown subscribe error: {!s} {!s}',
                              type(e), str(e))
            raise e
        return self.subscribed

    def wait(self):
        u""" Wait for updates.

        :returns bool:
            Returns true if an update is avaliable after `self.timeout` seconds
        """
        try:
            sel = select.select([self._conn], [], [], self.timeout)
        except select.error as e:
            self.logger.info(u'select interrupted: {!s}', str(e))
            return False
        return not (sel == ([], [], []))

    def fetch(self):
        u""" Fetch updates.

        :rtype: list, NoneType
        :return:
            A list of items, or None if unable to fetch updates.
        """
        import psycopg2
        try:
            self._conn.poll()
            self.logger.debug('Notifies: {!r}', self._conn.notifies)
            while self._conn.notifies:
                # We pop in the same order as items are added to notifies
                yield self._conn.notifies.pop(0)
        except psycopg2.OperationalError as e:
            self.logger.warn(u'Unable to poll source: {!s}', str(e))
            self._subscribed = False
        return

    def process(self):
        if not self.subscribed:
            if not self.subscribe(self.channels):
                time.sleep(self.timeout)
                return

        # Wait for something to happen on the connection
        if not self.wait():
            return

        for notification in self.fetch():
            # Extract channel and the event
            # Dictifying the event in order to pickle it when
            # enqueueuing.
            ev = self.db.get_event(int(notification.payload))
            # Append the channel and payload to the queue
            self.push(
                EventItem(
                    channel=str(notification.channel),
                    event=dict(ev)))

        # Rolling back to avoid IDLE in transact
        self.db.rollback()


class DBEventCollector(
        ProcessQueueMixin,
        ProcessDBMixin,
        ProcessLoopMixin,
        ProcessLoggingMixin):
    u""" Batch processing of Cerebrum.modules.EventLog events. """

    default_run_interval = 30
    default_failed_limit = 3
    default_failed_delay = 60
    default_abandon_limit = 90

    def __init__(self, channel, config={}, **kwargs):
        """ Event collector.

        This process runs periodically to look for failed and missed events.

        """
        self.target_system = channel
        self.run_interval = config.get('run_interval',
                                       self.default_run_interval)
        self.failed_limit = config.get('fail_limit',
                                       self.default_failed_limit)
        self.failed_delay = config.get('failed_delay',
                                       self.default_failed_delay)
        self.unpropagated_delay = config.get('unpropagated_delay',
                                             self.default_abandon_limit)
        super(DBEventCollector, self).__init__(**kwargs)

    def setup(self):
        super(DBEventCollector, self).setup()
        self.target_system = self.co.TargetSystem(self.target_system)
        self.db.rollback()

    def proocess(self):
        tmp_db = Factory.get('Database')(client_encoding='UTF-8')
        for x in tmp_db.get_unprocessed_events(self.target_system,
                                               self.failed_limit,
                                               self.failed_delay,
                                               self.unpropagated_delay,
                                               include_taken=True):
            self.push(
                EventItem(
                    channel=str(self.target_system),
                    event=dict(x)))
        tmp_db.close()

        # Sleep for a while
        time.sleep(self.run_interval)
