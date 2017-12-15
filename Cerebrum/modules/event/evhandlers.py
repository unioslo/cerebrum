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
""" Processes to handle events from the Cerebrum.modules.EventLog module."""
import time
import select
import traceback

from Cerebrum import Errors
from Cerebrum.Utils import Factory

from .errors import EventExecutionException
from .errors import EventHandlerNotImplemented

from .processes import ProcessDBMixin
from .processes import ProcessLoggingMixin
from .processes import ProcessLoopMixin
from .processes import ProcessQueueMixin
from .processes import QueueListener


class EventItem(object):
    """ Event Item to pass between queues. """

    __slots__ = ['channel', 'identifier', 'payload']

    def __init__(self, channel, identifier, payload):
        self.channel = channel
        self.identifier = identifier
        self.payload = payload

    def __repr__(self):
        return ('<{0.__class__.__name__}'
                ' ch={0.channel!r}'
                ' id={0.identifier!r}>').format(self)


class DBConsumer(ProcessDBMixin, ProcessLoggingMixin, QueueListener):
    """ Abstract class to handle database events.

    This process takes events from a queue, and processes it:

      1. Lock the event from other DBConsumers
      2. Handle the event (`handle_event`)
      3. Report event state back to the DB

    """

    # Abstract methods
    # TODO: Is it better to implement these as no-op methods rather than
    # raising a NotImplementedError? Or should we keep this as-is and force
    # subclasses to override if event management are no-ops?

    def _lock_event(self, identifier):
        """ acquire lock on the event. """
        raise NotImplementedError("Abstract method")

    def _release_event(self, identifier):
        """ release lock on the event. """
        raise NotImplementedError("Abstract method")

    def _remove_event(self, identifier):
        """ remove/mark event as completed. """
        raise NotImplementedError("Abstract method")

    def handle_event(self, event_object):
        """ Handle the EventItem. """
        raise NotImplementedError("Abstract method")

    # Lock/event management.
    # These methods manages db commit/rollback, and should not be neccessary to
    # override.

    def __lock_event(self, identifier):
        """ Acquire lock on event.

        :param identifier:
            An identifier used to find and lock the event.

        :return bool:
            True if locked, False otherwise.
        """
        self.db.rollback()
        if self._lock_event(identifier):
            self.db.commit()
            return True
        else:
            self.logger.debug(u'Unable to lock event %r', identifier)
            self.db.rollback()
            return False

    def __release_event(self, identifier):
        """ Remove lock on event.

        :param identifier:
            An identifier used to find and release the event.

        :return bool:
            True if unlocked, False otherwise.
        """
        self.db.rollback()
        if self._release_event(identifier):
            self.db.commit()
            return True
        else:
            self.logger.warn(u'Unable to release event %r', identifier)
            self.db.rollback()
            return False

    def __remove_event(self, identifier):
        """ Remove an event

        :param identifier:
            An identifier used to find and lock the event.

        :return bool:
            True if removed, False otherwise.
        """
        self.db.rollback()
        if self._remove_event(identifier):
            self.db.commit()
            return True
        else:
            self.logger.warn(u'Unable to remove event %r', identifier)
            self.db.rollback()
            return False

    def handle(self, item):
        """ Process event.

        :param item:
            The item fetched from the queue.
        """
        if not isinstance(item, EventItem):
            self.logger.error(u'Invalid event: %r', item)

        self.logger.debug2(u'Got a new event on channel %r: id=%r event=%r',
                           item.channel, item.identifier, item.payload)

        if not self.__lock_event(item.identifier):
            return

        try:
            self.handle_event(item.payload)
            if not self.__remove_event(item.identifier):
                return
            self.db.commit()

        except EventExecutionException as e:
            # If an event fails, we just release it, and let the
            # DelayedNotificationCollector enqueue it when appropriate
            self.logger.debug(u'Failed to process event_id %d: %s',
                              item.identifier, e)
            self.__release_event(item.identifier)

        except EventHandlerNotImplemented as e:
            self.logger.debug(u'No event handlers for event %r: %s', item, e)
            self.__release_event(item.identifier)

        except Exception as e:
            # What happened here? We have an unhandled error,
            # which is bad. Log it!
            #
            # We don't release the "lock" on the event, since the event
            # will probably fail the next time around. Manual intervention
            # is therefore REQUIRED!
            tb = traceback.format_exc()
            tb = '\t' + tb.replace('\n', '\t\n')
            self.logger.error(u'Unhandled error!\n%s\n%s',
                              item.payload, tb)


class DBProducer(
        ProcessQueueMixin,
        ProcessDBMixin,
        ProcessLoopMixin,
        ProcessLoggingMixin):
    """ Class to push items to a DBConsumer. """
    def push(self, item):
        """ Push an event_log row onto the queue.

        This method transforms the row to a EventItem tuple.

        :param dict db_row:
            A db_row, see `EventLog.get_event()`.
        """
        try:
            super(DBProducer, self).push(item)
        except Exception as e:
            self.logger.error(u'Unable to push db event %r: %s', item, e)


class DBListener(DBProducer):
    """ Producer for EventConsumer processes.

    This process LISTENs for Postgres notifications. When a notification is
    pushed, this process will fetch the actual events and push them onto a
    shared queue.

    You'll probably want to override the _build_event method, to fetch and/or
    insert custom data into the EventItem payload.
    """

    def __init__(self, channels=None, **kwargs):
        """ Sets up listening channels.

        :param list channels:
            A list of channels to subscribe to
        """
        if not channels:
            raise ValueError("no channels")
        self.channels = channels or []
        super(DBListener, self).__init__(**kwargs)

    @property
    def subscribed(self):
        """ Subscription status. """
        if not hasattr(self, '_subscribed'):
            self._subscribed = False
        return self._subscribed

    @subscribed.setter
    def subscribed(self, value):
        self._subscribed = bool(value)

    def subscribe(self, channels):
        """ Subscribe to channels. """
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
            self.logger.warn(u'Unable to subscribe: %s', e)
        except Exception as e:
            self.logger.error(u'Unknown subscribe error: %s %s', type(e), e)
            raise e
        return self.subscribed

    def wait(self):
        """ Wait for updates.

        :returns bool:
            Returns true if an update is avaliable after `self.timeout` seconds
        """
        try:
            sel = select.select([self._conn], [], [], self.timeout)
        except select.error as e:
            self.logger.info(u'select interrupted: %s', e)
            return False
        return not (sel == ([], [], []))

    def fetch(self):
        """ Fetch updates.

        :rtype: list, NoneType
        :return:
            A list of items, or None if unable to fetch updates.
        """
        import psycopg2
        try:
            self._conn.poll()
            self.logger.debug('Notifies: %r', self._conn.notifies)
            while self._conn.notifies:
                # We pop in the same order as items are added to notifies
                yield self._conn.notifies.pop(0)
        except psycopg2.OperationalError as e:
            self.logger.warn(u'Unable to poll source: %s', e)
            self._subscribed = False
        return

    def _build_event(self, notification):
        """ notification -> EventItem """
        return EventItem(notification.channel,
                         id(notification),
                         notification.payload)

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
            self.push(self._build_event(notification))

        # Rolling back to avoid IDLE in transact
        self.db.rollback()


class EventLogConsumer(DBConsumer):
    """ Class to handle Cerebrum.modules.EventLog events.

    The actual event handling is abstract (`handle_event`), and should be
    implemented in subclasses.
    """
    def _lock_event(self, event_id):
        try:
            self.db.lock_event(event_id)
            return True
        except Errors.NotFoundError:
            return False

    def _release_event(self, event_id):
        try:
            self.db.release_event(event_id)
            return True
        except Errors.NotFoundError:
            return False

    def _remove_event(self, event_id):
        try:
            self.db.remove_event(event_id)
            return True
        except Errors.NotFoundError:
            return False

    def get_event_code(self, event):
        """ Get a ChangeType from the event.

        :param dict event:
            The event.

        :return ChangeType:
            Returns the ChangeType code referred to in the event['event_type'].
        """
        try:
            return self.co.ChangeType(int(event['event_type']))
        except KeyError as e:
            self.logger.warn(u'Invalid event format for %r: %s', event, e)
        except Exception as e:
            self.logger.warn(u'Unable to process event %r: %s', event, e)
        return None

    def handle_event(self, event):
        """ Call the appropriate handlers.

        :param event:
            The event to process.
        """
        key = self.get_event_code(event)
        if not key:
            return
        self.logger.debug3(u'Got event key %r', key)

        raise EventHandlerNotImplemented(
            u'Abstract event handler called')


class EventLogMixin(DBProducer):
    """ Implements serializing db-rows from mod_eventlog to EventItems. """

    def _row_to_event(self, db_row):
        channel = str(self.co.TargetSystem(db_row['target_system']))
        identity = int(db_row['event_id'])
        event = dict(db_row)
        return EventItem(channel, identity, event)


class EventLogListener(EventLogMixin, DBListener):
    def _build_event(self, notification):
        db_row = self.db.get_event(int(notification.payload))
        return self._row_to_event(db_row)


class EventLogCollector(EventLogMixin, DBProducer):
    """ Batch processing of Cerebrum.modules.EventLog events. """

    def __init__(self, channel, config={}, **kwargs):
        """ Event collector.

        This process runs periodically to look for failed and missed events.

        """
        self.target_system = channel
        self.config = config
        super(EventLogCollector, self).__init__(**kwargs)

    def setup(self):
        super(EventLogCollector, self).setup()
        self.target_system = self.co.TargetSystem(self.target_system)
        self.db.rollback()

    def process(self):
        tmp_db = Factory.get('Database')(client_encoding=self.db_enc)
        for db_row in tmp_db.get_unprocessed_events(
                self.target_system,
                self.config['failed_limit'],
                self.config['failed_delay'],
                self.config['unpropagated_delay'],
                include_taken=True):
            self.push(self._row_to_event(db_row))
        tmp_db.close()

        self.logger.debug2("Ping!")

        # Sleep for a while
        time.sleep(self.config['run_interval'])
