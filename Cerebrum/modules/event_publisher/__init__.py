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
""" Translate changes to event messages and publish them.

This module is intended to send changelog entries to a Sevice bus, Message
Queue or Message Broker.

"""

import json

import Cerebrum.ChangeLog
import Cerebrum.DatabaseAccessor
from Cerebrum.Utils import Factory
from Cerebrum import Errors

__version__ = '1.0'


def get_client():
    """Instantiate publishing client.

    Instantiated trough the defined config."""
    from Cerebrum.config import get_config
    from Cerebrum.Utils import dyn_import
    conf = get_config(__name__.split('.')[-1])
    (mod_name, class_name) = conf.get('client').split('/', 1)
    client = getattr(dyn_import(mod_name), class_name)
    return client(conf)


def change_type_to_message(db, change_type_code, subject,
                           dest, change_params):
    """Convert change type to message dicts."""
    constants = Factory.get("Constants")(db)

    def get_entity_type(entity_id):
        entity = Factory.get("Entity")(db)
        try:
            ent = entity.get_subclassed_object(id=entity_id)
            return (entity_id,
                    ent,
                    str(constants.EntityType(ent.entity_type)))
        except Errors.NotFoundError:
            return (entity_id, None, None)

    def get_entity_name(entity_id):
        try:
            (_, en, en_type) = get_entity_type(entity_id)
            from cereconf import ENTITY_TYPE_NAMESPACE
            namespace = constants.ValueDomain(
                ENTITY_TYPE_NAMESPACE.get(en_type, None))
            return en.get_name(namespace)
        except (AttributeError, TypeError, Errors.NotFoundError):
            return None

    if change_params:
        change_params = change_params.copy()
    else:
        change_params = dict()
    if subject:
        (subjectid, subject, subjecttype) = get_entity_type(subject)
    else:
        subjectid = subjecttype = None
    if dest:
        (destid, dest, desttype) = get_entity_type(dest)
    else:
        destid = desttype = None
    if 'spread' in change_params:
        context = str(constants.Spread(change_params['spread']))
        del change_params['spread']
    else:
        context = None
    import Cerebrum.modules.event_publisher.converters as c
    return c.filter_message({
        'category': change_type_code.category,
        'change': change_type_code.type,
        'context': context,
        'subjectid': subjectid,
        'subjecttype': subjecttype,
        'subjectname': get_entity_name(subjectid),
        'objectid': destid,
        'objecttype': desttype,
        'objectname': get_entity_name(destid),
        'data': change_params,
    },
        subject, dest, change_type_code, db)


class EventPublisher(Cerebrum.ChangeLog.ChangeLog):
    """ Class used to publish changes to an external system.

    This class is intended to be used with a Message Broker.
    """

    def cl_init(self, **kw):
        super(EventPublisher, self).cl_init(**kw)
        self.__queue = []
        self.__client = None
        self.__unpublished_events = None

    def log_change(self,
                   subject_entity,
                   change_type_id,
                   destination_entity,
                   change_params=None,
                   skip_publish=False,
                   **kw):
        """ Queue a change to be published. """
        super(EventPublisher, self).log_change(
            subject_entity,
            change_type_id,
            destination_entity,
            change_params=change_params,
            **kw)

        if skip_publish:
            return

        data = change_type_to_message(self, change_type_id,
                                      subject_entity,
                                      destination_entity,
                                      change_params)
        # Conversion can discard data by returning false value
        if not data:
            return
        self.__queue.append(data)

    def clear_log(self):
        """ Clear local queue """
        super(EventPublisher, self).clear_log()
        self.__queue = []

    def publish_log(self):
        """ Publish messages. """
        super(EventPublisher, self).publish_log()
        if self.__queue:
            self.__try_send_messages()

    def __get_client(self):
        if not self.__client:
            self.__client = get_client()
        return self.__client

    def __get_unpublished_events(self):
        if not self.__unpublished_events:
            self.__unpublished_events = UnpublishedEvents(self)
        return self.__unpublished_events

    def __try_send_messages(self):
        try:
            client = self.__get_client()
            ue = self.__get_unpublished_events()
            unsent = ue.query_events(lock=True, parse_json=True)
            for event in unsent:
                client.publish(event['message'])
                ue.delete_event(event['eventid'])
            while self.__queue:
                message = self.__queue[0]
                client.publish(message)
                del self.__queue[0]
        except Exception as e:
            Factory.get_logger("cronjob") \
                .error("Could not write message: %s", e)
            self.__save_queue()

    def __save_queue(self):
        """Save queue to event queue"""
        ue = self.__get_unpublished_events()
        ue.add_events(self.__queue)
        self.__queue = []


class UnpublishedEvents(Cerebrum.DatabaseAccessor.DatabaseAccessor):
    """
    Events that could not be published due to …

    If there is an error, we need to store the event until
    it can be sent.
    """
    def __init__(self, database):
        super(UnpublishedEvents, self).__init__(database)
        self._db = database
        self._lock = None

    def _acquire_lock(self, lock=True):
        if lock and self._lock is None:
            self._lock = self._db.cursor().acquire_lock(
                table='[:table schema=cerebrum name=unpublished_events]')

    def query_events(self, lock=False, parse_json=False):
        self._acquire_lock(lock)
        ret = self.query("""
                         SELECT *
                         FROM [:table schema=cerebrum name=unpublished_events]
                         ORDER BY eventid ASC
                         """)
        if parse_json:
            loads = json.loads

            def fix(row):
                row['message'] = loads(row['message'])
                return row
            ret = map(fix, ret)
        return ret

    def delete_event(self, eventid):
        self._acquire_lock()
        self.execute("""DELETE
                     FROM [:table schema=cerebrum name=unpublished_events]
                     WHERE eventid = :eventid""", {'eventid': eventid})

    def add_events(self, events):
        self._acquire_lock()
        qry = """INSERT INTO [:table schema=cerebrum name=unpublished_events]
                 (tstamp, eventid, message)
                 VALUES
                 (DEFAULT,
                 [:sequence schema=cerebrum name=eventpublisher_seq op=next],
                 :event)"""
        dumps = json.dumps
        for event in events:
            # From python docs: use separators to get compact encoding
            self.execute(qry, {'event': dumps(event,
                                              separators=(',', ':'),
                                              encoding=self._db.encoding)})


if __name__ == '__main__':
    pass
    # Demo
