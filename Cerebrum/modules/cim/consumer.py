
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
from Cerebrum.utils.funcwrap import memoize

from Cerebrum.Utils import Factory
import pickle


class default_config(object):
    u""" Mock config. """

    client = {
        'url': 'http://localhost:80',
        'version': 'v1'
    }

    event = {
        'run_interval': 30,
        'fail_limit': 3,
        'fail_delay': 60,
        'abandon_limit': 90
    }

    def __getitem__(self, name):
        for prefix in ('client', 'event'):
            if name == prefix:
                return getattr(self, name)
            if '.' in name:
                pre, key = name.split('.', 1)
                if pre == prefix:
                    return getattr(self, prefix)[key]
        raise KeyError(u'No config {!r}'.format(name))


class Listener(evhandlers.EventConsumer):
    u""" Event listener and handler for CIM. """

    event_map = EventMap()

    def __init__(self, cim_mock=False, cim_config=default_config(), **kwargs):
        # TODO Replace with real config
        self.__config = cim_config
        self.__mock = cim_mock
        super(Listener, self).__init__(**kwargs)

    def handle_event(self, event):
        u""" Call the appropriate handlers.

        :param event:
            The event to process.
        """
        key = str(self.get_event_code(event))
        self.logger.debug3(u'Got event key {!r}', str(key))

        for callback in self.event_map.get_callbacks(str(key)):
            try:
                callback(self, key, event)
            except (EntityTypeError, UnrelatedEvent) as e:
                self.logger.debug3(
                    u'callback {!r} failed for event {!r} ({!r}): {!s}',
                    callback, key, event, e)

    @property
    @memoize
    def client(self):
        # TODO: Really use memoize here?
        # TODO: return real, initialized client?
        if self.__mock or True:
            class _mock_cim_client(object):
                def __init__(s, c):
                    s.config = c

                def __getattribute__(s, n):
                    def _log(*a, **kw):
                        self.logger.info('MOCK: {!s}({!r}, {!r})', n, a, kw)
                    return _log
            return _mock_cim_client(self.__config['client'])

    @event_map(
        'e_account:create',
        'e_account:mod',
        'e_account:password')
    def account_change(self, key, event):
        u""" Account change - update CIM. """
        pe = Factory.get('Person')(self.db)
        ac = Factory.get('Account')(self.db)

        ac.find(event['subject_entity'])
        if ac.owner_type != self.co.entity_person:
            self.logger.debug3('Invalid owner type {!r}', ac.owner_type)
            # TODO: What if account owner has changed from person to group?
            #       Can that happen?
            return

        pe.find(ac.owner_id)

        # TODO: Replace with real client call
        self.client.update_person(pe.entity_id)

    @event_map(
        'ac_type:add',
        'ac_type:mod',
        'ac_type:del')
    def account_pri_change(self, key, event):
        u""" Account priority change! """
        pe = Factory.get('Person')(self.db)
        ac = Factory.get('Account')(self.db)

        ac.find(event['subject_entity'])
        if ac.owner_type != self.co.entity_person:
            self.logger.debug3('Invalid owner type {!r}', ac.owner_type)
            return
        pe.find(ac.owner_id)

        # 1. List all pe users.
        # 2. Check current pri vs params pri?
        # 2. Del all non-pri
        # 3. Del or update pri, if eligible

        pri_account = pe.get_primary_account()

        self.logger.info(u'Current primary account: {:d}', pri_account)
        self.logger.info(u'Current account: {:d}', ac.entity_id)

        params = event.get('change_params')
        if params:
            try:
                params = pickle.loads(params)
            except Exception as e:
                params = e

        # TODO: Replace with real client calls
        self.client.update_person(key, pe.entity_id)

    @event_map('e_account:delete', 'e_account:destroy')
    def account_delete(self, key, event):
        self.logger.info(u'Account delete (can this happen?): {!r}', event)

    @event_map(
        'person:create',
        'person:update')
    def person_change(self, key, event):
        u""" Person change - update CIM. """
        pe = Factory.get('Person')(self.db)
        ac = Factory.get('Account')(self.db)

        pe.find(ac.owner_id)
        account_id = pe.get_primary_account()
        ac.find(account_id)

        # TODO: Replace with real client call
        self.client.update_person(key, pe.entity_id)

    @event_map(
        'person:name_del',
        'person:name_add',
        'person:name_mod')
    def person_name_change(self, key, event):
        u""" Person name change - update CIM. """
        pe = Factory.get('Person')(self.db)
        ac = Factory.get('Account')(self.db)

        pe.find(ac.owner_id)
        account_id = pe.get_primary_account()
        ac.find(account_id)

        # TODO: Replace with real client call
        self.client.update_person(key, pe.entity_id)

    @event_map(
        'person:aff_add',
        'person:aff_mod',
        'person:aff_del')
    def person_aff_change(self, key, event):
        u""" Person aff change - update CIM. """
        pe = Factory.get('Person')(self.db)
        ac = Factory.get('Account')(self.db)

        pe.find(ac.owner_id)
        account_id = pe.get_primary_account()
        ac.find(account_id)

        # TODO: Decide on delete or update
        # So much could have happened here!

        # TODO: Replace with real client call
        self.client.update_person(key, pe.entity_id)
