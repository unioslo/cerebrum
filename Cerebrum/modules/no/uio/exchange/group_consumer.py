#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2016 University of Oslo, Norway
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
"""Event-handler for Exchange events."""

from __future__ import unicode_literals

import os
import traceback

from urllib2 import URLError

from six import text_type

from Cerebrum.modules.exchange.Exceptions import (ExchangeException,
                                                  ServerUnavailableException,
                                                  AlreadyPerformedException)
from Cerebrum.modules.event.errors import (EntityTypeError,
                                           EventExecutionException,
                                           UnrelatedEvent)
from Cerebrum.modules.exchange.CerebrumUtils import CerebrumUtils
from Cerebrum.Utils import Factory
from Cerebrum.utils.funcwrap import memoize


from Cerebrum.modules.event.mapping import EventMap
from Cerebrum.modules.event import evhandlers

from . import group_flattener


class ExchangeGroupEventHandler(evhandlers.EventLogConsumer):
    """Event handler for Exchange.

    This event handler is started by the event daemon.
    It implements functions that are called based on wich ChangeTypes they are
    associated with, trough the event_map decorator.
    """

    event_map = EventMap()

    def __init__(self, config, mock=False, **kwargs):
        """ExchangeGroupEventHandler initialization routine.

        :type config: dict
        :param config: Dict containing the config for the ExchangeClient
            and handler

        :type event_queue: multiprocessing.Queue
        :param event_queue: The queue that events get queued on

        :type logger: multiprocessing.Queue
        :param logger: Put tuples like ('warn', 'my message') onto this
            queue in order to have them logged

        :type run_state: multiprocessing.Value(ctypes.c_int)
        :param run_state: A shared object used to determine if we should
            stop execution or not

        :type mock: bool
        :param mock: Wether to run in mock-mode or not
        """
        self.config = config

        self.mock = mock

        # Group lookup patterns
        self.group_name_translation = \
            dict(self.config.selection_criteria.group_name_translations)
        # Group defining that rendzone users should be shown in address book
        self.randzone_unreserve_group = \
            self.config.selection_criteria.randzone_publishment_group

        super(ExchangeGroupEventHandler, self).__init__(**kwargs)
        self.logger.debug2("Started event handler class: %s" % self.__class__)

    @property
    @memoize
    def co(self):
        return Factory.get('Constants')(self.db)

    @property
    @memoize
    def mb_spread(self):
        return self.co.Spread(
            self.config.selection_criteria.mailbox_spread)

    @property
    @memoize
    def group_spread(self):
        return self.co.Spread(
            self.config.selection_criteria.group_spread)

    @property
    @memoize
    def shared_mbox_spread(self):
        return self.co.Spread(
            self.config.selection_criteria.shared_mbox_spread)

    @property
    @memoize
    def ad_spread(self):
        return self.co.Spread(
            self.config.selection_criteria.ad_spread)

    @property
    @memoize
    def ut(self):
        return CerebrumUtils()

    def cleanup(self):
        super(ExchangeGroupEventHandler, self).cleanup()
        # Kill existing PS-Session before shutting down
        self.ec.kill_session()
        self.ec.close()
        self.logger.info('ExchangeGroupEventHandler stopped')

    @property
    @memoize
    def ec(self):
        """Get an instantiated Exchange Client to use for communicating

        :rtype Cerebrum.modules.no.uio.exchange.ExchangeClient.ExchangeClient

        """
        if self.mock:
            self.logger.info('Running in mock-mode')
            from Cerebrum.modules.no.uio.exchange.ExchangeClient import (
                ClientMock as excclass, )
        else:
            from Cerebrum.modules.no.uio.exchange.ExchangeClient import (
                ExchangeClient as excclass, )

        def j(*l):
            return '\\'.join(l)
        auth_user = (j(self.config.client.auth_user_domain,
                       self.config.client.auth_user) if
                     self.config.client.auth_user_domain else
                     self.config.client.auth_user)

        exchange_commands = dict(self.config.client.exchange_commands)

        try:
            return excclass(
                auth_user=auth_user,
                domain_admin=j(self.config.client.domain_reader_domain,
                               self.config.client.domain_reader),
                ex_domain_admin=j(
                    self.config.client.exchange_admin_domain,
                    self.config.client.exchange_admin),
                management_server=self.config.client.management_host,
                exchange_commands=exchange_commands,
                session_key=self._gen_key(),
                logger=self.logger,
                host=self.config.client.jumphost,
                port=self.config.client.jumphost_port,
                ca=self.config.client.ca,
                client_key=self.config.client.client_key,
                client_cert=self.config.client.client_cert,
                check_name=self.config.client.hostname_verification,
                encrypted=self.config.client.enabled_encryption)
        except URLError, e:
            # Here, we handle the rare circumstance that the springboard is
            # down when we connect to it. We log an error so someone can
            # act upon this if it is appropriate.
            self.logger.error(
                "Can't connect to springboard! Please notify postmaster!")
            raise ServerUnavailableException(text_type(e))
        except Exception as e:
            # Get the traceback, put some tabs in front, and log it.
            tb = traceback.format_exc()
            self.logger.error("ExchangeClient failed setup:\n%s" % tb)
            raise ServerUnavailableException(text_type(e))

    def _gen_key(self):
        """Return a unique key for the current process

        :rtype: text_type

        """
        return 'CB%s' % hex(os.getpid())[2:].upper()

    def handle_event(self, event):
        u""" Call the appropriate handlers.

        :param event:
            The event to process.
        """
        key = text_type(self.get_event_code(event))
        self.logger.debug3('Got event key %r', key)

        for callback in self.event_map.get_callbacks(key):
            try:
                callback(self, event)
            except (EntityTypeError, UnrelatedEvent) as e:
                self.logger.debug3(
                    'Callback %r failed for event %r (%r): %s',
                    callback, key, event, e)

    @event_map('exchange:group_add')
    def add_group_members(self, event):
        """Addition of member to group.

        :type event: Cerebrum.extlib.db_row.row
        :param event: The event returned from Change- or EventLog.

        :raise UnrelatedEvent: If this event is unrelated to this handler.
        :raise EventExecutionException: If the event fails to execute."""
        group_id = group_flattener.get_entity(self.db, event['subject_entity'])
        member = group_flattener.get_entity(self.db, event['dest_entity'])
        if not member:
            return
        (destinations, candidates) = group_flattener.add_operations(
            self.db, self.co,
            member, group_id,
            self.group_spread, self.mb_spread)
        for (group_id, group_name) in destinations:
            for (entity_id, entity_name) in candidates:
                try:
                    self.ec.add_distgroup_member(group_name, entity_name)
                    self.logger.info(
                        'eid:{event_id}: Added {entity_name} to '
                        '{group_name}'.format(
                            event_id=event['event_id'],
                            entity_name=entity_name,
                            group_name=group_name))
                    # Copy & mangle the event, so we can log it correctly
                    mod_ev = event.copy()
                    mod_ev['dest_entity'] = entity_id
                    mod_ev['subject_entity'] = group_id
                    self.ut.log_event_receipt(mod_ev, 'dlgroup:add')
                except AlreadyPerformedException:
                    pass
                except (ExchangeException, ServerUnavailableException), e:
                    self.logger.warn(
                        'eid:{event_id}: Can\'t add {entity_name} to '
                        '{group_name}: {reason}'.format(
                            event_id=event['event_id'],
                            entity_name=entity_name,
                            group_name=group_name,
                            reason=e))
                    raise EventExecutionException

    @event_map('exchange:group_rem')
    def remove_group_member(self, event):
        """Removal of member from group.

        :type event: Cerebrum.extlib.db_row.row
        :param event: The event returned from Change- or EventLog.

        :raise UnrelatedEvent: Raised if the event is not to be handled."""
        group_id = group_flattener.get_entity(self.db, event['subject_entity'])
        member = group_flattener.get_entity(self.db, event['dest_entity'])
        if not member:
            return
        removals = group_flattener.remove_operations(self.db, self.co,
                                                     member, group_id,
                                                     self.group_spread,
                                                     self.mb_spread)

        if not removals:
            return
        for (group_id, group_name) in removals.keys():
            for (cand_id, cand_name) in removals.get((group_id, group_name)):
                try:
                    self.ec.remove_distgroup_member(group_name, cand_name)
                    self.logger.info(
                        'eid:{event_id}: Removed {cand_name} from '
                        '{group_name}'.format(event_id=event['event_id'],
                                              cand_name=cand_name,
                                              group_name=group_name))
                    # Copy & mangle the event, so we can log it reciept
                    # correctly
                    mod_ev = event.copy()
                    mod_ev['dest_entity'] = cand_id
                    mod_ev['subject_entity'] = group_id
                    self.ut.log_event_receipt(mod_ev, 'dlgroup:rem')
                except AlreadyPerformedException:
                    pass
                except (ExchangeException, ServerUnavailableException), e:
                    self.logger.warn(
                        'eid:{event_id}: Can\'t remove {cand_name} from '
                        '{group_name}: {error}'.format(
                            event_id=event['event_id'], cand_name=cand_name,
                            group_name=group_name, error=e))
