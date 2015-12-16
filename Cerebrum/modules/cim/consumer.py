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
u""" This module contains a consumer for Cerebrum events. """
from Cerebrum.modules.event.EventExceptions import EntityTypeError
from Cerebrum.modules.event.EventExceptions import UnrelatedEvent
from Cerebrum.modules.event.mapping import EventMap
from Cerebrum.modules.event import evhandlers
from Cerebrum.utils.funcwrap import memoize

from Cerebrum.modules.cim.client import CIMClient
from Cerebrum.modules.cim.datasource import CIMDataSource

from Cerebrum.Utils import Factory
import pickle


class Listener(evhandlers.EventConsumer):
    u""" Event listener and handler for CIM. """

    event_map = EventMap()

    def __init__(self, cim_config, cim_mock=False, **kwargs):
        self._config = cim_config
        self._mock = cim_mock
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
    def datasource(self):
        return CIMDataSource(db=self.db,
                             config=self._config.datasource)

    @property
    @memoize
    def client(self):
        if self._mock:
            class _mock_cim_client(object):
                def __getattribute__(s, n):
                    def _log(*a, **kw):
                        self.logger.info('MOCK: {!s}({!r}, {!r})', n, a, kw)
                    return _log
            return _mock_cim_client()
        return CIMClient(config=self._config.client,
                         logger=self.logger)

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

        userdata = self.datasource.get_person_data(pe.entity_id)
        self.client.update_user(userdata)

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

        userdata = self.datasource.get_person_data(pe.entity_id)
        self.client.update_user(userdata)

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

        pe.find(event['subject_entity'])
        account_id = pe.get_primary_account()
        if not account_id:
            self.logger.warning(
                "person_id:{} has no primary account, skipping")
            raise UnrelatedEvent
        ac.find(account_id)

        userdata = self.datasource.get_person_data(pe.entity_id)
        self.client.update_user(userdata)

    @event_map(
        'person:name_del',
        'person:name_add',
        'person:name_mod')
    def person_name_change(self, key, event):
        u""" Person name change - update CIM. """
        pe = Factory.get('Person')(self.db)
        ac = Factory.get('Account')(self.db)

        pe.find(event['subject_entity'])
        account_id = pe.get_primary_account()
        if not account_id:
            self.logger.warning(
                "person_id:{} has no primary account, skipping")
            raise UnrelatedEvent
        ac.find(account_id)

        userdata = self.datasource.get_person_data(pe.entity_id)
        self.client.update_user(userdata)

    @event_map(
        'person:aff_add',
        'person:aff_mod',
        'person:aff_del')
    def person_aff_change(self, key, event):
        u""" Person aff change - update CIM. """
        pe = Factory.get('Person')(self.db)
        ac = Factory.get('Account')(self.db)

        pe.find(event['subject_entity'])
        account_id = pe.get_primary_account()
        if not account_id:
            self.logger.warning(
                "person_id:{} has no primary account, skipping")
            raise UnrelatedEvent
        ac.find(account_id)

        # TODO: Decide on delete or update
        # So much could have happened here!

        userdata = self.datasource.get_person_data(pe.entity_id)
        self.client.update_user(userdata)
