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
""" An abstract event that can be stored in the database. """
from __future__ import absolute_import

import datetime
import itertools
import mx.DateTime
import pytz

import cereconf


class _VerbSingleton(type):
    """ A metaclass that makes each EventType verb a singleton. """

    verbs = {}

    def __call__(cls, verb, *args):
        if verb not in cls.verbs:
            cls.verbs[verb] = super(_VerbSingleton, cls).__call__(verb, *args)
        return cls.verbs[verb]

    def get_verb(cls, verb):
        return cls.verbs.get(verb)


class EventType(_VerbSingleton('EventTypeSingleton', (object,), {})):
    """Holds an event type."""

    __slots__ = ['verb', 'description', ]

    def __init__(self, verb, description):
        """ Initialize EventType.

        :verb: Scim verb
        :description: HR description text
        """
        self.verb = verb
        self.description = description

    def __repr__(self):
        return '<{0.__class__.__name__!s} {0.verb}>'.format(self)

    def __eq__(self, other):
        """Equality."""
        return isinstance(other, EventType) and other.verb == self.verb

    def __hash__(self):
        """Hash."""
        return hash(self.verb)


# Define event types:

ADD = EventType('add', 'Add an object to subject')
CREATE = EventType('create', 'Create a new subject')
ACTIVATE = EventType('activate', 'Subject has no longer quarantines in system')
MODIFY = EventType('modify', 'Attributes has changed')
DEACTIVATE = EventType('deactivate', 'Quarantine is activated')
DELETE = EventType('delete', 'Subject is deleted')
REMOVE = EventType('remove', 'Remove an object from subject')
PASSWORD = EventType('password', 'Subject has changed password')
JOIN = EventType('join', 'Join two objects')


class EntityRef(object):
    """ Representation of a single entity.

    The entity_id can be used internally to identify which object we reference

    The entity_type and ident is used to generate a reference to the object
    that other systems can use.
    """

    __slots__ = ['ident', 'entity_type', 'entity_id', ]

    def __init__(self, entity_id, entity_type, ident):
        self.entity_id = int(entity_id)
        self.entity_type = entity_type
        self.ident = ident

    def __repr__(self):
        return ("<{0.__class__.__name__}"
                " id={0.entity_id!r}"
                " type={0.entity_type!r}"
                " ident={0.ident!r}>").format(self)

    def __eq__(self, other):
        return (isinstance(other, EntityRef) and
                self.entity_id == other.entity_id)

    def to_dict(self):
        return {
            'ident': self.ident,
            'entity_id': self.entity_id,
            'entity_type': self.entity_type, }


class DateTimeDescriptor(object):
    """ Datetime descriptor that handles timezones.

    When setting the datetime, this method will try to localize it with the
    default_timezone in the following ways:

    - mx.DateTime.DateTimeType: Naive datetime, assume in default_timezone
    - datetime.datetime: Assume in default_timezone if naive
    - integer: Assume timestamp in UTC

    The returned object will always be a localized datetime.datetime

    """

    default_timezone = pytz.timezone(cereconf.TIMEZONE)

    def __init__(self, slot):
        """ Creates a new datetime descriptor.

        :param str slot:
            The attribute name where the actual value is stored.
        """
        self.slot = slot

    def __repr__(self):
        return '{0.__class__.__name__}({0.slot!r})'.format(self)

    def __get__(self, obj, cls=None):
        if not obj:
            return self
        return getattr(obj, self.slot, None)

    def __set__(self, obj, value):
        if value is None:
            self.__delete__(obj)
            return

        if isinstance(value, (int, long, )):
            # UTC timestamp
            value = pytz.utc.localize(
                datetime.datetime.fromtimestamp(value))
        elif isinstance(value, mx.DateTime.DateTimeType):
            # Naive datetime in default_timezone
            value = self.default_timezone.localize(value.pydatetime())
        elif isinstance(value, datetime.datetime):
            if value.tzinfo is None:
                value = self.default_timezone.localize(value)
        else:
            raise TypeError('Invalid datetime {0} ({1})'.format(type(value),
                                                                repr(value)))

        setattr(obj, self.slot, value)

    def __delete__(self, obj):
        if hasattr(obj, self.slot):
            delattr(obj, self.slot)


class Event(object):
    """ Event abstraction.

    Contains all the neccessary data to serialize an event.
    """

    DEFAULT_TIMEZONE = 'Europe/Oslo'

    __slots__ = ['event_type', 'subject', 'objects', 'context', 'attributes',
                 '_timestamp', '_scheduled', ]

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

    def __repr__(self):
        return ('<{0.__class__.__name__}'
                ' event={0.event_type!r}'
                ' subject={0.subject!r}>').format(self)

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
