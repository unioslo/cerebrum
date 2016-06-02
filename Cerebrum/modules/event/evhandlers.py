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
import pickle
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


# EventItem = namedtuple('EventItem', ('channel',
#                                      'channel_id',
#                                      'event',
#                                      'event_id',
#                                      'index',
#                                      'timestamp',
#                                      'subject',
#                                      'destination',
#                                      'params',
#                                      'failed',
#                                      'taken_time',))
# u""" Simple event representation for the queue. """


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

    def __lock_event(self, event_id):
        u""" Acquire lock on event.

        :param int event_id:
            The event id to lock

        :return bool:
            True if locked, False otherwise.
        """
        try:
            self.db.lock_event(event_id)
            self.db.commit()
            return True
        except Errors.NotFoundError:
            self.logger.debug(u'Unable to lock event {!r}', event_id)
            self.db.rollback()
            return False

    def __release_event(self, event_id):
        u""" Remove lock on event.

        :param int event_id:
            The event id to unlock

        :return bool:
            True if unlocked, False otherwise.
        """
        try:
            self.db.release_event(event_id)
            self.db.commit()
            return True
        except Errors.NotFoundError:
            self.logger.warn(u'Unable to release event {!r}', event_id)
            self.db.rollback()
            return False

    def __remove_event(self, event_id):
        u""" Remove an event

        :param int event_id:
            The event id to remove.

        :return bool:
            True if removed, False otherwise.
        """
        try:
            self.db.remove_event(event_id)
            self.db.commit()
            return True
        except Errors.NotFoundError:
            self.logger.warn(u'Unable to remove event {!r}', event_id)
            self.db.rollback()
            return False

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

        if not self.__lock_event(ev['event_id']):
            return

        try:
            self.handle_event(ev)
            if not self.__remove_event(ev['event_id']):
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
            self.__release_event(ev['event_id'])

        except EventHandlerNotImplemented as e:
            self.logger.debug3('Unable to handle event_id {:d}: {!s}',
                               ev['event_id'], str(e))
            self.__remove_event(ev['event_id'])

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


class _DBEventProducer(
        ProcessQueueMixin,
        ProcessDBMixin,
        ProcessLoopMixin,
        ProcessLoggingMixin):

    def __event_to_item(self, event):
        u""" Format `get_event` db-row to EventItem. """
        # transform = {
        #     'channel': ('target_system',
        #                 lambda v: str(self.co.TargetSystem(v))),
        #     'channel_id': ('target_system',
        #                    lambda v: int(self.co.TargetSystem(v))),
        #     'event': ('event_type',
        #               lambda v: str(self.co.ChangeType(v))),
        #     'event_id': ('event_type',
        #                  lambda v: int(self.co.ChangeType(v))),
        #     'index': ('event_id', None),
        #     'timestamp': ('tstamp', None),
        #     'subject': ('subject_entity', None),
        #     'destination': ('dest_entity', None),
        #     'params': ('change_params',
        #                lambda v: pickle.loads(v) if v else None),
        #     'failed': ('failed', None),
        #     'taken_time': ('taken_time', None)
        # }
        transform = {
            'channel': ('target_system',
                        lambda v: str(self.co.TargetSystem(v))),
            'event': (None, dict), }

        args = {}
        for name, (from_key, transform) in transform.iteritems():
            if not callable(transform):
                transform = lambda x: x
            try:
                if from_key:
                    args[name] = transform(event[from_key])
                else:
                    args[name] = transform(event)
            except Exception as e:
                self.logger.debug('Unable to transform {!r} -> {!r}: {!s}',
                                  from_key, name, e)
                raise
        return EventItem(**args)

    def push(self, db_row):
        u""" Push a event_log row onto the queue.

        This method transforms the row to a EventItem tuple.

        :param dict db_row:
            A db_row, see `EventLog.get_event()`.
        """
        try:
            item = self.__event_to_item(db_row)
            super(_DBEventProducer, self).push(item)
        except Exception as e:
            self.logger.error(u'Unable to push db event {!r}: {!s}',
                              db_row, str(e))


class DBEventListener(_DBEventProducer):
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
            self.push(ev)

        # Rolling back to avoid IDLE in transact
        self.db.rollback()


class DBEventCollector(_DBEventProducer):
    u""" Batch processing of Cerebrum.modules.EventLog events. """

    def __init__(self, channel, config={}, **kwargs):
        """ Event collector.

        This process runs periodically to look for failed and missed events.

        """
        self.target_system = channel
        self.config = config
        super(DBEventCollector, self).__init__(**kwargs)

    def setup(self):
        super(DBEventCollector, self).setup()
        self.target_system = self.co.TargetSystem(self.target_system)
        self.db.rollback()

    def process(self):
        tmp_db = Factory.get('Database')(client_encoding='UTF-8')
        for x in tmp_db.get_unprocessed_events(
                self.target_system,
                self.config['failed_limit'],
                self.config['failed_delay'],
                self.config['unpropagated_delay'],
                include_taken=True):
            self.push(x)
        tmp_db.close()

        self.logger.debug2("Ping!")

        # Sleep for a while
        time.sleep(self.config['run_interval'])
