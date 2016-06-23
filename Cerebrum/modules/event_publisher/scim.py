#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016 University of Oslo, Norway
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

"""Implementation of SCIM messages.
https://tools.ietf.org/html/draft-hunt-idevent-scim-00#section-2.2
"""

import uuid
import time
import itertools
import mx.DateTime as dt
from Cerebrum.config.configuration import Configuration, ConfigDescriptor
from Cerebrum.config.settings import String


class EventType(object):

    """Holds an event type."""

    def __init__(self, verb, description):
        """Initialize EventType.

        :verb: Scim verb, or URI
        :description: HR description text
        """
        self.verb = verb
        self.uri = (verb if ':' in verb else
                    'urn:ietf:params:event:SCIM:{}'.format(verb))
        self.description = description

    def __str__(self):
        """Get URI."""
        return self.uri

    def __eq__(self, other):
        """Equality."""
        return isinstance(other, EventType) and other.uri == self.uri

    def __hash__(self):
        """Hash."""
        return hash(self.uri)


ADD = EventType('add', 'Add a spread to subject')
CREATE = EventType('create', 'Create a new subject')
ACTIVATE = EventType('activate', 'Subject has no longer quarantines in system')
MODIFY = EventType('modify', 'Attributes has changed')
DEACTIVATE = EventType('deactivate', 'Quarantine is activated')
DELETE = EventType('delete', 'Subject is deleted')
REMOVE = EventType('remove', 'Subject lost spread')
PASSWORD = EventType('password', 'Subject has changed password')


class EventConfig(Configuration):

    """Configuration for scim events"""

    issuer = ConfigDescriptor(String,
                              default=u'Cerebrum',
                              doc=u'Issuer field in scim')

    urltemplate = ConfigDescriptor(String,
                                   default='https://cerebrum.example.com/v1/'
                                   '{entity_type}/{entity_id}',
                                   doc=u'Format string for URL (use '
                                   '{entity_type} and {entity_id} as '
                                   'placeholders')

    keytemplate = ConfigDescriptor(String,
                                   default=u'no.uio.cerebrum.scim.{entity_type}'
                                   '.{event}',
                                   doc=u'Format string for routing key (use '
                                   '{entity_type} and {event} as '
                                   'placeholders')


class Event(object):

    """Represent a SCIM message payload."""

    def __init__(self, event, time=None, issuer=None, spreads=None,
                 subject=None, attributes=None, expire=None):
        """Initialize.

        :event: EventType object
        :time: time stamp (default = now)
        :issuer: issuer (default: config)
        :spreads: audience
        :subject: entity id or object
        :attributes: set of attributes
        :expire: expiry
        """
        self.event = event
        self.time = self.make_timestamp(time)
        self.issuer = self.issuer if issuer is None else issuer
        self.audience = self.make_aud(spreads, subject)
        self.subject = subject.entity_id
        self.attributes = set(attributes or [])
        self.expire = expire
        self.const = subject.const
        self.clconst = subject.clconst
        from Cerebrum.Person import Person
        from Cerebrum.Account import Account
        from Cerebrum.Group import Group
        from Cerebrum.OU import OU
        entity_type = 'entity'
        if isinstance(subject, Person):
            entity_type = 'person'
        elif isinstance(subject, Account):
            entity_type = 'account'
        elif isinstance(subject, Group):
            entity_type = 'group'
        elif isinstance(subject, OU):
            entity_type = 'ou'
        self.entity_type = entity_type
        self.key = self.make_key()

    @classmethod
    def load_config(cls):
        from Cerebrum.config.loader import read
        config = EventConfig()
        read(config, 'scim_event')
        config.validate()
        cls.issuer = config.issuer
        cls.url = config.urltemplate
        cls.keytemplate = config.keytemplate

    def make_timestamp(self, timestamp):
        """Convert arg to a timestamp."""
        if timestamp is None:
            return int(time.time())
        if isinstance(timestamp, dt.DateTime):
            return int(time.mktime(timestamp.timetuple()))
        return int(time)

    def make_key(self):
        """Return routing key"""
        return self.keytemplate.format(entity_type=self.entity_type,
                                       event=self.event.verb)

    def make_aud(self, aud, sub):
        """Make a default aud."""
        if aud:
            return set(aud)
        else:
            return set(sub.const.Spread(x['spread']) for x in sub.get_spread())

    def make_sub(self):
        """Convert arg into sub."""
        return self.url.format(entity_type=self.entity_type,
                               entity_id=self.subject)

    def get_event_uris(self):
        """Get list of event uris."""
        return [str(self.event)]

    def get_payload(self):
        """Create and return payload as jsonable dict."""
        ret = {
            'jti': str(uuid.uuid4()),
            'eventUris': self.get_event_uris(),
            'iat': self.time,
            'iss': self.issuer,
            'aud': list(str(x) for x in self.audience),
            'sub': self.make_sub()
        }
        if self.attributes:
            ret[str(self.event)] = {
                'attributes': list(self.attributes)
            }
        return ret

    def mergeable(self, other):
        """Can this be merged with other."""
        if self.subject != other.subject:
            return False
        if self.event == CREATE:
            return other.event not in (DEACTIVATE, REMOVE)
        if self.event == DELETE:
            return other.event in (REMOVE, DEACTIVATE, ADD, ACTIVATE, MODIFY,
                                   PASSWORD)
        if self.audience != other.audience:
            return False
        return True

    def merge(self, other):
        """Merge messages."""
        if not self.mergeable(other):
            return [self, other]
        if self.event == CREATE:
            if other.event == DELETE:
                return []
            if other.event == ADD:
                self.audience.update(other.audience)
                return [self]
            if other.event == ACTIVATE:
                return [self]  # TODO: if quarantine is an attr, delete it
            if other.event == MODIFY:
                self.attributes.update(other.attributes)
                return [self]
            if other.event == PASSWORD:
                self.attributes.add('password')
                return [self]
        elif self.event == DELETE:
            return [self]
        elif (ACTIVATE == self.event and DEACTIVATE == other.event and
              self.audience == other.audience):
            return []
        elif ADD == self.event and REMOVE == other.event and \
                self.audience == other.audience:
            return []
        elif self.event == other.event:
            if self.audience != other.audience:
                return [self, other]
            self.attributes.update(other.attributes)
            return [self]
        return [self, other]


Event.load_config()


def merge_payloads(payloads):
    """Merge payloads with similarities.

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
             REMOVE)
    ps = [[] for x in order]

    for pl in payloads:
        pltype = pl.event
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
                    rest = merged + rest
                    current = rest.pop(0)
                elif len(new) == 1:
                    rest.pop(0)
                else:
                    merged.append(rest.pop(0))
            else:
                finished.append(current)
                rest = merged
                merged = []
                current = rest.pop(0)
        finished.append(current)
        return finished

    for sub, lst in result.items():
        result[sub] = merge_list([], [], lst[0], lst[1:])
    return list(itertools.chain(*result.values()))
