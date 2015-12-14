
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
""" This module contains a consumer for Cerebrum events.

It is designed to be used with:

* The Cerebrum.modules.event message queue
* The servers/event/event_daemon.py event listener
* The .client WS-client.

"""
from Cerebrum.modules.event.EventExceptions import EntityTypeError
from Cerebrum.modules.event.EventExceptions import UnrelatedEvent
from Cerebrum.modules.event.mapping import EventMap
from Cerebrum.modules.event import evhandlers
# from Cerebrum.utils.funcwrap import memoize


class Listener(evhandlers.EventConsumer):
    u""" Event listener and handler for CIM. """

    event_map = EventMap()

    def handle_event(self, event):
        u""" Call the appropriate handlers.

        :param event:
            The event to process.
        """
        key = str(self.get_event_code(event))
        self.logger.debug3(u'Got event key {!r}', str(key))

        for callback in self.event_map.get_callbacks(str(key)):
            try:
                callback(self, event)
            except (EntityTypeError, UnrelatedEvent) as e:
                self.logger.debug3(
                    u'callback {!r} failed for event {!r} ({!r}): {!s}',
                    callback, key, event, e)

#   @property
#   @memoize
#   def client(self):
#       args = list()
#       kwargs = dict()

#       # TODO: return real, initialized client?
#       if self.mock or True:
#           return type(
#               '_mock_cim_client',
#               (object, ),
#               {'foo': lambda x: x * 2,
#                'bar': lambda x: x * 2, })(*args, **kwargs)

    @event_map('e_account:create', 'e_account:mod', 'e_account:password')
    def account_change(self, event):
        self.logger.info(u'Account change: {!r}', event)

# Typical `user create` flow
#
# e_account:create event
#   {'event_type': 374L,
#    'event_id': 4L,
#    'target_system': 955L,
#    'subject_entity': 878L,
#    'dest_entity': None,
#    'change_params':
#       "(dp0\nS'owner_type'\np1\nI835\nsS'account_name'\np2\nS'olano'\np3\nsS'creator_id'\np4\nL868L\nsS'owner_id'\np5\nL872L\ns.",
#    'tstamp': <mx.DateTime.DateTime object for '2015-12-11 18:21:38.00' at 7fb57b0b0078>,
#    'failed': 0L,
#    'taken_time': None,
#   }
#
# spread adds..
#
# e_account:mod event:
#   {'event_type': 269L,
#    'event_id': 8L,
#    'target_system': 955L,
#    'subject_entity': 878L,
#    'dest_entity': None,
#    'change_params': '(dp0\n.',
#    'tstamp': <mx.DateTime.DateTime object for '2015-12-11 18:21:38.00' at 7fb57b0b0078>,
#    'failed': 0L,
#    'taken_time': None,
#   }
#
# e_account:password event
#   {'event_type': 283L,
#    'event_id': 9L,
#    'target_system': 955L,
#    'subject_entity': 878L,
#    'dest_entity': None,
#    'change_params': "(dp0\nS'password'\np1\nS'kZ%&9)Lr'\np2\ns.",
#    'tstamp': <mx.DateTime.DateTime object for '2015-12-11 18:21:38.00' at 7fb57b0b0078>,
#    'failed': 0L,
#    'taken_time': None,
#   }
#
# ac_type:add event
#   {'event_type': 342L,
#    'event_id': 12L,
#    'target_system': 955L,
#    'subject_entity': 878L,
#    'dest_entity': None,
#    'change_params':
#       "(dp0\nS'priority'\np1\nI504\nsS'affiliation'\np2\nI726\nsS'ou_id'\np3\nI871\ns.",
#    'tstamp': <mx.DateTime.DateTime object for '2015-12-11 18:21:38.00' at 7fb57b0b0078>,
#    'failed': 0L,
#    'taken_time': None,
#   }

    @event_map('ac_type:add', 'ac_type:mod', 'ac_type:del')
    def account_type_change(self, event):
        self.logger.info(u'Account type change: {!r}', event)

    @event_map('e_account:delete', 'e_account:destroy')
    def delete_account(self, event):
        self.logger.info(u'Account delete (can this happen?): {!r}', event)

    @event_map(
        'person:create',
        'person:update',
        'person:name_del',
        'person:name_add',
        'person:name_mod',
        'person:aff_add',
        'person:aff_mod',
        'person:aff_del')
    def update_person(self, event):
        self.logger.info(u'Person change: {!r}', event)
