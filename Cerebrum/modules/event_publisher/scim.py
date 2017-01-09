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

import calendar
import itertools
import time
import uuid

import mx.DateTime as dt

from Cerebrum.config.configuration import Configuration, ConfigDescriptor
from Cerebrum.config.settings import String

from Cerebrum.Person import Person
from Cerebrum.Account import Account
from Cerebrum.Group import Group
from Cerebrum.OU import OU


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

    keytemplate = ConfigDescriptor(
        String,
        default=u'no.uio.cerebrum.scim.{entity_type}.{event}',
        doc=(u'Format string for routing key (use {entity_type} and {event} '
             u'as placeholders'))


class Event(object):
    """Represent a SCIM message payload."""

    def __init__(self,
                 event,
                 time=None,
                 issuer=None,
                 spreads=None,
                 subject=None,
                 attributes=None,
                 expire=None,
                 obj=None,
                 **extra):
        """Initialize.

        :event: EventType object
        :time: time stamp (default = now)
        :issuer: issuer (default: config)
        :spreads: audience
        :subject: entity id or object
        :attributes: set of attributes
        :expire: expiry
        :object: entity id or object
        """
        self.event = event
        self.time = self.make_timestamp(time)
        self.issuer = self.issuer if issuer is None else issuer
        self.audience = self.make_aud(spreads, subject)
        self.subject = self._get_identifier(subject)
        self.attributes = set(attributes or [])
        self.expire = expire
        self.const = subject.const
        self.clconst = subject.clconst
        self.extra = extra
        self.jti = str(uuid.uuid4())
        self.scheduled = None
        # TODO: Could these be gotten from REST API?
        # Or as an attribute of type?
        entity_type = 'entities'
        if isinstance(subject, Person):
            entity_type = 'persons'
        elif isinstance(subject, Account):
            entity_type = 'accounts'
        elif isinstance(subject, Group):
            entity_type = 'groups'
        elif isinstance(subject, OU):
            entity_type = 'ous'
        self.entity_type = entity_type
        if obj:
            self.obj = [self._get_identifier(obj)]
            entity_type = 'entities'
            if isinstance(obj, Person):
                entity_type = 'persons'
            elif isinstance(obj, Account):
                entity_type = 'accounts'
            elif isinstance(obj, Group):
                entity_type = 'groups'
            elif isinstance(obj, OU):
                entity_type = 'ous'
            self.obj_entity_type = [entity_type]
        else:
            self.obj = []
            self.obj_entity_type = []
        self.key = self.make_key()

    @staticmethod
    def _get_identifier(ent):
        if isinstance(ent, Account):
            return ent.account_name
        elif isinstance(ent, Group):
            return ent.group_name
        else:
            return ent.entity_id

    @classmethod
    def load_config(cls):
        from Cerebrum.config.loader import read
        config = EventConfig()
        read(config, 'scim-event')
        config.validate()
        cls.issuer = config.issuer
        cls.url = config.urltemplate
        cls.keytemplate = config.keytemplate

    def make_timestamp(self, timestamp):
        """Convert arg to a timestamp."""
        if timestamp is None:
            return int(time.time())
        if isinstance(timestamp, dt.DateTimeType):
            return int(time.mktime(timestamp.timetuple()))
        return int(timestamp)

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

    def make_obj(self):
        """Return obj in dict for payload"""
        return [self.url.format(entity_type=et,
                                entity_id=o)
                for o, et in zip(self.obj, self.obj_entity_type)]

    def get_event_uris(self):
        """Get list of event uris."""
        return [str(self.event)]

    def get_payload(self):
        """Create and return payload as jsonable dict."""
        ret = {
            'jti': self.jti,
            'eventUris': self.get_event_uris(),
            'iat': self.time,
            'iss': self.issuer,
            'aud': list(str(x) for x in self.audience),
            'sub': self.make_sub()
        }
        args = self.extra.copy()
        if self.attributes:
            args['attributes'] = list(self.attributes)
        if self.obj:
            args['object'] = self.make_obj()
        if args:
            ret[str(self.event)] = args
        if self.scheduled is not None:
            # assume datetime.datetime, although mx.DateTime will also work
            # .strftime('%s') is not official and it will not work in Windows
            ret['nbf'] = calendar.timegm(self.scheduled.timetuple())
        ret['resourceType'] = self.entity_type
        return ret

    def mergeable(self, other):
        """Can this be merged with other."""
        if self.scheduled is not None:
            return False
        if self.subject != other.subject:
            return False
        if self.event == CREATE:
            return other.event not in (DEACTIVATE, REMOVE)
        if self.event == DELETE:
            return other.event in (REMOVE, DEACTIVATE, ADD, ACTIVATE, MODIFY,
                                   PASSWORD)
        if self.event == other.event and self.event in (ADD, REMOVE, ACTIVATE,
                                                        DEACTIVATE):
            return True
        if self.audience != other.audience:
            return False
        return True

    def merge(self, other):
        """Merge messages."""
        def ret_self():
            self.obj.extend(other.obj)
            self.obj_entity_type.extend(other.obj_entity_type)
            return [self]

        if not self.mergeable(other):
            return [self, other]
        if self.event == CREATE:
            if other.event == DELETE:
                return []
            if other.event == ADD:
                self.audience.update(other.audience)
                return ret_self()
            if other.event == ACTIVATE:
                return ret_self()  # TODO: if quarantine is an attr, delete it
            if other.event == MODIFY:
                self.attributes.update(other.attributes)
                return ret_self()
            if other.event == PASSWORD:
                self.attributes.add('password')
                return ret_self()
        elif self.event == DELETE:
            return ret_self()
        elif other.event == DELETE:
            return [other]
        elif (ACTIVATE == self.event and DEACTIVATE == other.event and
              self.audience == other.audience):
            return []
        elif ADD == self.event and REMOVE == other.event and \
                self.audience == other.audience:
            return []
        elif self.event == other.event:
            if self.event in (ADD, REMOVE, ACTIVATE, DEACTIVATE):
                self.audience.update(other.audience)
                return ret_self()
            if self.audience != other.audience:
                return [self, other]
            self.attributes.update(other.attributes)
            return ret_self()
        return [self, other]


class ManualEvent(Event):
    def __init__(self,
                 event,
                 time=None,
                 subject=None,
                 subject_type=None,
                 attributes=None,
                 obj=None,
                 obj_entity_type=None,
                 **extra):
        self.event = event
        self.time = self.make_timestamp(time)
        self.subject = subject
        self.entity_type = subject_type
        self.key = self.make_key()
        self.jti = str(uuid.uuid4())
        self.scheduled = None
        self.attributes = set(attributes or [])
        self.audience = set()
        self.extra = extra
        self.obj = obj or []
        self.obj_entity_type = obj_entity_type or []


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
