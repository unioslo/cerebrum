# encoding: utf-8
#
# Copyright 2017-2024 University of Oslo, Norway
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
"""
Events that can be queued in the events table.

This module defines the :class:`.Event`, an abstract notification event that we
can store in the *events* table for later publishing.

The event stores data that is de-coupled from the rest of the database.  This
includes re-mapping our *change type* to :class:`.EventType`, and referring to
cerebrum entities with :class:`.EntityRef` objects.

The *Event* object should contain all neccessary data for the messages that are
to be published, as we don't want to look up (potentially out-of-date) data
when publishing these events.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import itertools

import six

from Cerebrum.utils import date as date_utils
from Cerebrum.utils import date_compat
from Cerebrum.utils import reprutils


class _VerbSingleton(type):
    """ A metaclass that makes each EventType verb a singleton. """

    verbs = {}

    def __call__(cls, verb, *args):
        if verb not in cls.verbs:
            cls.verbs[verb] = super(_VerbSingleton, cls).__call__(verb, *args)
        return cls.verbs[verb]

    def get_verb(cls, verb):
        return cls.verbs.get(verb)


@six.add_metaclass(_VerbSingleton)
class EventType(reprutils.ReprFieldMixin):
    """ The event type definition - each *verb* results in a singleton. """

    __slots__ = ('verb', 'description')

    repr_id = False
    repr_module = False
    repr_fields = ('verb',)

    def __init__(self, verb, description):
        """ Initialize EventType.

        :verb: Scim verb
        :description: HR description text
        """
        self.verb = verb
        self.description = description

    def __eq__(self, other):
        """Equality."""
        return isinstance(other, EventType) and other.verb == self.verb

    def __hash__(self):
        """Hash."""
        return hash(self.verb)


# Define common event types:

CREATE = EventType("create", "Create a new subject")
MODIFY = EventType("modify", "Attributes has changed")
DELETE = EventType("delete", "Subject is deleted")

ACTIVATE = EventType("activate", "Subject has no longer quarantines in system")
DEACTIVATE = EventType("deactivate", "Quarantine is activated")

ADD = EventType("add", "Add an object to subject")
REMOVE = EventType("remove", "Remove an object from subject")

PASSWORD = EventType("password", "Subject has changed password")
JOIN = EventType("join", "Join two objects")


class EntityRef(reprutils.ReprFieldMixin):
    """
    Representation of a single subject or object.

    The *entity_id* can be used internally to identify which subject or object
    an Event refers to.

    The *entity_type* and *ident* is used to generate a reference to the
    subject or object for other systems.
    """
    __slots__ = ('_values',)
    fields = ('entity_id', 'entity_type', 'ident')

    repr_id = False
    repr_module = False
    repr_fields = fields

    def __init__(self, entity_id, entity_type, ident):
        self._values = (int(entity_id), entity_type, ident)

    @property
    def entity_id(self):
        return self._values[0]

    @property
    def entity_type(self):
        return self._values[1]

    @property
    def ident(self):
        return self._values[2]

    def __hash__(self):
        return hash(self._values)

    def __eq__(self, other):
        return (isinstance(other, EntityRef) and
                self.entity_id == other.entity_id)

    def to_dict(self):
        return dict(zip(self.fields, self._values))


class DateTimeDescriptor(reprutils.ReprEvalMixin):
    """ Datetime descriptor that handles timezones.

    When setting the datetime, this method will try to localize it in the
    following ways:

    - date or naive datetime-like: assume in local tz (see get_datetime_tz)
    - tz-aware datetime.datetime: Convert to local timezone
    - integer: Assume timestamp in UTC

    The returned object will always be a localized datetime.datetime
    """

    repr_id = False
    repr_module = False
    repr_args = ('slot',)

    def __init__(self, slot):
        """ Creates a new datetime descriptor.

        :param str slot:
            The attribute name where the actual value is stored.
        """
        self.slot = slot

    def __get__(self, obj, cls=None):
        if not obj:
            return self
        return getattr(obj, self.slot, None)

    def __set__(self, obj, value):
        if value is None:
            self.__delete__(obj)
            return

        if isinstance(value, six.integer_types):
            value = date_utils.from_timestamp(value)
        else:
            value = date_compat.get_datetime_tz(value)
        setattr(obj, self.slot, value)

    def __delete__(self, obj):
        if hasattr(obj, self.slot):
            delattr(obj, self.slot)


class Event(reprutils.ReprFieldMixin):
    """
    Event abstraction.

    Contains all the neccessary data to serialize an event.
    """

    __slots__ = ('event_type', 'subject', 'objects', 'context', 'attributes',
                 '_timestamp', '_scheduled')

    repr_id = False
    repr_module = False
    repr_fields = ('event_type', 'subject')

    timestamp = DateTimeDescriptor('_timestamp')
    scheduled = DateTimeDescriptor('_scheduled')

    def __init__(self, event_type,
                 subject=None,
                 objects=None,
                 context=None,
                 attributes=None,
                 timestamp=None,
                 scheduled=None):
        """
        :param EventType event: the type of event
        :param EntityRef subject: reference to the affected entity
        :param list objects: sequence of other affected objects (EntityRef)
        :param list context: sequence of affected systems (str)
        :param list attributes: sequence of affected attributes (str)
        :param datetime timestamp: when the event originated
        :param datetime schedule: when the event should be issued
        """
        self.event_type = event_type
        self.subject = subject
        self.timestamp = timestamp
        self.scheduled = scheduled
        self.objects = set(objects or [])
        self.context = set(context or [])
        self.attributes = set(attributes or [])

    def mergeable(self, other):
        """Can this event be merged with other."""

        if self.scheduled is not None:
            return False
        if self.subject != other.subject:
            return False
        if self.event_type == CREATE:
            return other.event_type not in (DEACTIVATE, REMOVE)
        if self.event_type == DELETE:
            return other.event_type in (REMOVE, DEACTIVATE, ADD, ACTIVATE,
                                        MODIFY, PASSWORD)
        if (self.event_type == other.event_type and
                self.event_type in (ADD, REMOVE, ACTIVATE, DEACTIVATE)):
            return True
        if self.context != other.context:
            return False
        return True

    def merge(self, other):
        """Merge messages."""
        def ret_self():
            self.objects.update(other.objects)
            return [self]

        if not self.mergeable(other):
            return [self, other]
        if self.event_type == CREATE:
            if other.event_type == DELETE:
                return []
            if other.event_type == ADD:
                self.context.update(other.context)
                return ret_self()
            if other.event_type == ACTIVATE:
                return ret_self()  # TODO: if quarantine is an attr, delete it
            if other.event_type == MODIFY:
                self.attributes.update(other.attributes)
                return ret_self()
            if other.event_type == PASSWORD:
                self.attributes.add('password')
                return ret_self()
        elif self.event_type == DELETE:
            return ret_self()
        elif other.event_type == DELETE:
            return [other]
        elif (ACTIVATE == self.event_type and
              DEACTIVATE == other.event_type and
              self.context == other.context):
            return []
        elif (ADD == self.event_type and
              REMOVE == other.event_type and
              self.context == other.context):
            return []
        elif self.event_type == other.event_type:
            if self.event_type in (ADD, REMOVE, ACTIVATE, DEACTIVATE):
                self.context.update(other.context)
                return ret_self()
            if self.context != other.context:
                return [self, other]
            self.attributes.update(other.attributes)
            return ret_self()
        return [self, other]


def merge_events(events):
    """Merge events with similarities.

    As long as subject is the same:
    * create + add/activate/modify/password = create with attributes merged
    * create + deactivate/remove is untouched
    * create + delete should be removed

    * delete + remove/deactivate/add/activate/modify/password = delete

    * x + x = x
    * activate + deactivate = noop (careful with aud)

    Sort into canonical order:
    #. create
    #. delete
    #. add
    #. activate
    #. modify
    #. password
    #. deactivate
    #. remove
    """
    order = (CREATE, DELETE, ADD, ACTIVATE, MODIFY, PASSWORD, DEACTIVATE,
             REMOVE, JOIN)
    ps = [[] for x in order]

    for pl in events:
        pltype = pl.event_type
        idx = order.index(pltype)
        ps[idx].append(pl)

    result = {}
    for idx, tp, pl in zip(range(len(order)), order, ps):
        for p in pl:
            if p.subject not in result:
                result[p.subject] = [p]
            else:
                result[p.subject].append(p)

    def merge_list(finished, merged, current, rest):
        while rest or merged:
            if rest:
                new = current.merge(rest[0])
                if not new:
                    rest.pop(0)
                    merged.extend(rest)
                    rest = merged
                    if not rest:
                        return finished
                    merged = []
                    current = rest.pop(0)
                elif len(new) == 1:
                    if new[0] is not current:
                        merged.extend(rest)
                        rest = merged
                        current = rest.pop(0)
                        merged = []
                    else:
                        rest.pop(0)
                else:
                    merged.append(rest.pop(0))
            else:  # merged is not empty
                finished.append(current)
                rest = merged
                merged = []
                current = rest.pop(0)
        finished.append(current)
        return finished

    for sub, lst in result.items():
        result[sub] = merge_list([], [], lst[0], lst[1:])
    return list(itertools.chain(*result.values()))
