#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015-2018 University of Oslo, Norway
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
""" This module contains a consumer for Cerebrum events. """

from __future__ import unicode_literals, absolute_import

import Cerebrum.utils.json as json

from six import text_type

from Cerebrum.modules.event.errors import EntityTypeError
from Cerebrum.modules.event.errors import UnrelatedEvent
from Cerebrum.modules.event.errors import EventExecutionException
from Cerebrum.modules.event.errors import EventHandlerNotImplemented
from Cerebrum.modules.event.mapping import EventMap
from Cerebrum.modules.event import evhandlers
from Cerebrum.utils.funcwrap import memoize

from .client import CIMClient

from Cerebrum.Errors import NotFoundError
from Cerebrum.Utils import Factory, dyn_import


class CimConsumer(evhandlers.EventLogConsumer):
    """ Event listener and handler for CIM. """

    event_map = EventMap()

    def __init__(self, cim_config, cim_mock=False, **kwargs):
        self._config = cim_config
        self._mock = cim_mock
        super(CimConsumer, self).__init__(**kwargs)

    def handle_event(self, event):
        """ Call the appropriate handlers.

        :param event:
            The event to process.
        """
        key = text_type(self.get_event_code(event))
        self.logger.debug3('Got event key %r', key)

        try:
            event_handlers = self.event_map.get_callbacks(key)
        except EventHandlerNotImplemented:
            self.logger.info('No event handlers for event key %r', key)
            return

        for callback in event_handlers:
            try:
                callback(self, key, event)
            except (EntityTypeError, UnrelatedEvent) as e:
                self.logger.debug3(
                    'Callback %r failed for event %r (%r): %s',
                    callback, key, event, e)

    @property
    @memoize
    def datasource(self):
        mod, name = self._config.datasource.datasource_class.split('/')
        mod = dyn_import(mod)
        cls = getattr(mod, name)
        return cls(db=self.db,
                   config=self._config.datasource,
                   logger=self.logger)

    @property
    @memoize
    def client(self):
        if self._mock:
            class _mock_cim_client(object):
                def __getattribute__(s, n):
                    def _log(*a, **kw):
                        self.logger.info('MOCK: %s(%r, %r)', n, a, kw)
                    return _log
            return _mock_cim_client()
        return CIMClient(config=self._config.client,
                         logger=self.logger)

    def update_user(self, key, event, person_id):
        self.logger.info(
            "eid:{} {}: "
            "Fetching data and updating user for person_id:{}".format(
                event['event_id'], key, person_id))
        userdata = self.datasource.get_person_data(person_id)
        if userdata is None:
            self.logger.warning(
                "eid:{}: {}: "
                "Failed to gather data for person_id:{}, skipping".format(
                    event['event_id'],
                    key,
                    person_id))
            raise UnrelatedEvent
        if not self.client.update_user(userdata):
            self.logger.error(
                "eid:{}: {}: "
                "Failed to add/update user account:{!r} person_id:{}".format(
                    event['event_id'],
                    key,
                    userdata.get('username'),
                    person_id))
            raise EventExecutionException
        return True

    def delete_user(self, key, event, username):
        self.logger.info(
            "eid:{}: {}: Deleting user {!r}".format(
                event['event_id'], key, username))
        if not self.client.delete_user(username):
            self.logger.error(
                "eid:{}: {}: "
                "Could not delete user {!r}".format(
                    event['event_id'], key, username))
            raise EventExecutionException
        return True

    def delete_users_for_person(self, key, event, person_id,
                                except_account_id):
        ac = Factory.get('Account')(self.db)
        all_accounts = [x['account_id'] for x in
                        ac.search(owner_id=person_id,
                                  expire_start=None)]
        to_delete = [a for a in all_accounts if a != except_account_id]
        for account_id in to_delete:
            ac.clear()
            ac.find(account_id)
            self.delete_user(key, event, ac.account_name)
        return True

    @event_map(
        'account:create',
        'account:modify',
        'account_password:set')
    def account_change(self, key, event):
        """ Account change """
        pe = Factory.get('Person')(self.db)
        ac = Factory.get('Account')(self.db)

        ac.find(event['subject_entity'])
        if ac.owner_type != self.co.entity_person:
            raise UnrelatedEvent

        pe.find(ac.owner_id)
        if not self.datasource.is_eligible(pe.entity_id):
            return UnrelatedEvent

        self.update_user(key, event, pe.entity_id)

    @event_map(
        'account_type:add',
        'account_type:modify',
        'account_type:remove')
    def account_pri_change(self, key, event):
        """ Account priority change """
        pe = Factory.get('Person')(self.db)
        ac = Factory.get('Account')(self.db)

        ac.find(event['subject_entity'])
        if ac.owner_type != self.co.entity_person:
            raise UnrelatedEvent

        pe.find(ac.owner_id)
        new_primary = None

        if self.datasource.is_eligible(pe.entity_id):
            new_primary = pe.get_primary_account()
            # Make sure the current primary account exists
            if new_primary:
                self.update_user(key, event, pe.entity_id)

        # Delete all other accounts
        self.delete_users_for_person(key, event, pe.entity_id,
                                     except_account_id=new_primary)

    @event_map(
        'person:create',
        'person:modify')
    def person_change(self, key, event):
        """ Person change """
        pe = Factory.get('Person')(self.db)
        try:
            pe.find(event['subject_entity'])
        except NotFoundError:
            raise UnrelatedEvent
        if not self.datasource.is_eligible(pe.entity_id):
            return UnrelatedEvent
        self.update_user(key, event, pe.entity_id)

    @event_map(
        'person_name:remove',
        'person_name:add',
        'person_name:modify')
    def person_name_change(self, key, event):
        """ Person name change """
        pe = Factory.get('Person')(self.db)
        try:
            pe.find(event['subject_entity'])
        except NotFoundError:
            raise UnrelatedEvent
        if not self.datasource.is_eligible(pe.entity_id):
            return UnrelatedEvent
        self.update_user(key, event, pe.entity_id)

    @event_map(
        'entity_cinfo:add',
        'entity_cinfo:remove')
    def entity_cinfo_change(self, key, event):
        """ Person contact info change """
        pe = Factory.get('Person')(self.db)
        try:
            pe.find(event['subject_entity'])
        except NotFoundError:
            raise UnrelatedEvent

        if not self.datasource.is_eligible(pe.entity_id):
            return UnrelatedEvent
        self.update_user(key, event, pe.entity_id)

    @event_map(
        'spread:add',
        'spread:remove')
    def spread_change(self, key, event):
        """ Spread change """
        change_params = json.loads(event['change_params'])
        if change_params.get('spread', 0) != int(self.datasource.spread):
            raise UnrelatedEvent

        pe = Factory.get('Person')(self.db)
        try:
            pe.find(event['subject_entity'])
        except NotFoundError:
            raise UnrelatedEvent

        primary = None
        if self.datasource.is_eligible(pe.entity_id):
            primary = pe.get_primary_account()
            # Make sure the current primary account exists
            if primary:
                self.update_user(key, event, pe.entity_id)

        # Delete all other accounts
        self.delete_users_for_person(key, event, pe.entity_id,
                                     except_account_id=primary)

    @event_map(
        'person_aff:add',
        'person_aff:modify',
        'person_aff:remove',
        'person_aff_src:add',
        'person_aff_src:modify',
        'person_aff_src:remove')
    def person_aff_change(self, key, event):
        """ Person aff change. """
        pe = Factory.get('Person')(self.db)
        try:
            pe.find(event['subject_entity'])
        except NotFoundError:
            raise UnrelatedEvent
        new_primary = None

        if self.datasource.is_eligible(pe.entity_id):
            new_primary = pe.get_primary_account()
            # Make sure the current primary account exists
            if new_primary:
                self.update_user(key, event, pe.entity_id)

        # Delete all other accounts
        self.delete_users_for_person(key, event, pe.entity_id,
                                     except_account_id=new_primary)
