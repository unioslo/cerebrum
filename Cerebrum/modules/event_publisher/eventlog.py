# encoding: utf-8
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
""" Changelog mixin that stores changes as database events.

The process is:

1. `log_change` takes ChangeLog-parameters, and converts them to an
   `event.Event` object using `change_type_to_event`.
2. `write_log` attempts to merge a series of events using `event.merge_events`,
    and writes the result to the database.

A separate consumer process (from the `consumer` module) reads these event
entries, and makes sure that messages are sent to an actual MQ.

NOTE:

Any log_change call can be scheduled by adding a datetime or timestamp to
`change_params['schedule']`. This is mostly for testing and debugging.


TODO: change_params should carry as much info as possible. It should include:

- Relevant data about the entity itself (EntityName, EntitySpread,
entity_type).  That way, we don't need to do additional lookups when doing
`write_log`. Most of the info needs to be fetched by the entity anyway...
- Relevant data about the change. E.g. 'start', 'end' and 'disable_until' for
quarantine changes.

"""
from __future__ import absolute_import

import copy
import six

from Cerebrum.ChangeLog import ChangeLog
from Cerebrum.Entity import EntitySpread
from Cerebrum.Errors import NotFoundError
from Cerebrum.Utils import Factory
from .converters import EventFilter
from .event import merge_events
from .eventdb import EventsAccessor
from .utils import get_entity_ref

try:
    from cereconf import ENTITY_TYPE_NAMESPACE
except ImportError:
    ENTITY_TYPE_NAMESPACE = dict()


def get_entity_spreads(db, entity_id):
    """ Lookup any entity spreads on an entity.

    entity_id -> [<spread_code_str>, ...]
    """
    # TODO: Include spreads in change_params, so that we don't have to look
    #       them up?
    constants = Factory.get("Constants")(db)
    entity = EntitySpread(db)
    try:
        entity.find(int(entity_id))
        return [six.text_type(constants.Spread(s['spread']))
                for s in entity.get_spread()]
    except (NotFoundError, ValueError):
        pass
    return list()


def change_type_to_event(db, change_type, subject_id, dest_id, params):
    """ Get an event from changelog-params.

    :return Event:
        Return an Event-object for the change, or None if no Event should be
        sent for this change.

    """
    constants = Factory.get("Constants")(db)

    msg = {'category': change_type.category,
           'change': change_type.type,
           'context': None,
           'subject': None,
           'objects': [],
           'data': copy.copy(params) if params else dict(),
           'payload': None, }

    if subject_id:
        msg['subject'] = get_entity_ref(db, subject_id)

    if dest_id:
        msg['objects'].append(get_entity_ref(db, dest_id))

    if 'spread' in msg['data']:
        msg['context'] = [six.text_type(constants.Spread(msg['data']['spread'])), ]
        del msg['data']['spread']
    else:
        msg['context'] = get_entity_spreads(db, subject_id)

    f = EventFilter(db)
    return f(msg, change_type)


def create_event(db, event_object):
    """ Write an Event object to the database. """
    events = EventsAccessor(db)

    event_data = dict()
    if event_object.attributes:
        event_data['attributes'] = list(event_object.attributes)
    if event_object.context:
        event_data['context'] = list(event_object.context)
    if event_object.objects:
        event_data['objects'] = [
            {'object_id': o.entity_id,
             'object_type': o.entity_type,
             'object_ident': o.ident, }
            for o in event_object.objects]

    return events.create_event(
        event_object.event_type.verb,
        event_object.subject.entity_id,
        event_object.subject.entity_type,
        event_object.subject.ident,
        schedule=event_object.scheduled,
        data=event_data)


class EventLog(ChangeLog):
    """Class used for registring and managing events."""

    # TODO: Shouldn't EventLog inherit from Database?

    # Don't want to override the Database constructor
    def cl_init(self, **kw):
        super(EventLog, self).cl_init(**kw)
        self.__events = []

    # TODO: Rename this to log_event, and make all apropriate callers
    # of log_change compatible. Also, make better docstrings!
    def log_change(self,
                   subject_entity,
                   change_type,
                   destination_entity,
                   change_params=None,
                   skip_publish=False,
                   **kw):
        """Register events that should be stored into the database. """
        super(EventLog, self).log_change(
            subject_entity,
            change_type,
            destination_entity,
            change_params=change_params,
            **kw)

        if skip_publish:
            # Ugh
            return

        # TODO: Ugh, we don't inherit from the database but expect to behave
        # like it by passing self as a database object...
        message = change_type_to_event(self,
                                       change_type,
                                       subject_entity,
                                       destination_entity,
                                       change_params)
        if message is not None:
            self.__events.append(message)

    def clear_log(self):
        """ Remove events in queue for writing. """
        super(EventLog, self).clear_log()
        self.__events = []

    def write_log(self):
        """ Commit new events to the event log. """
        super(EventLog, self).write_log()

        for e in merge_events(self.__events):
            create_event(self, e)

        self.__events = []

    @property
    def queued_events(self):
        return self.__events[:]
