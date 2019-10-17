#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2017 University of Oslo, Norway
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
""" MQ-publishing event_log consumer.

This consumer implementation takes any message published to the event_log, and
re-publishes it using the specified AMQP client implementation/configuration.

"""
# import json
import datetime
import time

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.event import evhandlers
from Cerebrum.utils.funcwrap import memoize

from .eventdb import EventsAccessor, from_row
from . import EVENT_CHANNEL, get_client, get_formatter


class EventConsumer(evhandlers.DBConsumer):

    def __init__(self, publisher_config, formatter_config, **kwargs):
        self.publisher_config = publisher_config
        self.formatter_config = formatter_config
        super(EventConsumer, self).__init__(**kwargs)

    @property
    @memoize
    def event_db(self):
        return EventsAccessor(self.db)

    @property
    @memoize
    def publisher(self):
        """ Message Queue client. """
        return get_client(self.publisher_config)

    @property
    @memoize
    def formatter(self):
        return get_formatter(self.formatter_config)

    def _lock_event(self, event_id):
        """ acquire lock on the event. """
        try:
            self.event_db.lock_event(event_id)
            return True
        except Errors.NotFoundError:
            return False

    def _release_event(self, identifier):
        """ release lock on the event. """
        try:
            self.event_db.fail_count_inc(identifier)
            self.event_db.release_event(identifier)
            return True
        except Errors.NotFoundError:
            return False

    def _remove_event(self, identifier):
        """ remove/mark event as completed. """
        try:
            self.event_db.delete_event(identifier)
            return True
        except Errors.NotFoundError:
            return False

    def handle_event(self, event):
        """ Publish event using message queue client. """

        self.logger.debug("Trying to publish {!r}".format(event))

        message = self.formatter(event)

        routing_key = self.formatter.get_key(event.event_type, event.subject)

        # Publish message
        with self.publisher as client:
            client.publish(routing_key, message)
            self.logger.info('Message published (msg jti={0})'
                             ''.format(message['jti']))


class EventListener(evhandlers.DBListener):

    def __init__(self, **kwargs):
        kwargs['channels'] = [EVENT_CHANNEL, ]
        super(EventListener, self).__init__(**kwargs)

    @property
    def event_db(self):
        try:
            self.__event_db
        except AttributeError:
            self.__event_db = EventsAccessor(self.db)
        return self.__event_db

    def _build_event(self, notification):
        db_row = self.event_db.get_event(int(notification.payload))
        return evhandlers.EventItem(
            notification.channel, int(db_row['event_id']), from_row(db_row))


class EventCollector(evhandlers.DBProducer):
    """ Periodically fetch DB-events and push them onto the event queue. """

    def __init__(self, config={}, **kwargs):
        self.config = config
        super(EventCollector, self).__init__(**kwargs)

    def process(self):
        _now = datetime.datetime.utcnow
        start = _now()
        tmp_db = Factory.get('Database')(client_encoding='UTF-8')
        event_db = EventsAccessor(tmp_db)
        for db_row in event_db.get_unprocessed(
                self.config['failed_limit'],
                self.config['failed_delay'],
                self.config['unpropagated_delay']):
            event = evhandlers.EventItem(
                EVENT_CHANNEL, int(db_row['event_id']), from_row(db_row))
            self.push(event)
        tmp_db.close()

        # Ensure process() takes run_interval seconds, by sleeping in
        # self.timeout intervals
        while self.running:
            if (_now() - start).total_seconds() > self.config['run_interval']:
                # We've used at least run_interval seconds
                break

            time.sleep(self.timeout)
