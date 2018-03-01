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

import traceback
from urllib2 import URLError

from six import text_type

from Cerebrum.modules.exchange.Exceptions import (ExchangeException,
                                                  ServerUnavailableException)
from Cerebrum.modules.event.errors import (EventExecutionException,
                                           EntityTypeError,
                                           UnrelatedEvent)
from Cerebrum.modules.event.mapping import EventMap
from Cerebrum.modules.no.uio.exchange.consumer import (
    ExchangeEventHandler as UIOExchangeEventHandler,)
from Cerebrum import Errors
from Cerebrum.utils.funcwrap import memoize


class ExchangeEventHandler(UIOExchangeEventHandler):
    """
    Event handler for Exchange made for UiA.

    Inherits Cerebrum.modules.exchange.ExchangeEventHandler.
    ExchangeEventHandler
    """

    event_map = EventMap()

    @property
    @memoize
    def ec(self):
        """Get an instantiated Exchange Client to use for communicating

        :rtype ExchangeClient.ExchangeClient

        """
        if self.mock:
            self.logger.info('Running in mock-mode')
            from Cerebrum.modules.no.uio.exchange.ExchangeClient import (
                ClientMock as excclass, )
        else:
            from Cerebrum.modules.no.hia.exchange.ExchangeClient import (
                UiAExchangeClient as excclass, )

        def j(*l):
            return '\\'.join(l)
        auth_user = (j(self.config.client.auth_user_domain,
                       self.config.client.auth_user) if
                     self.config.client.auth_user_domain else
                     self.config.client.auth_user)
        try:
            return excclass(
                auth_user=auth_user,
                domain_admin=j(self.config.client.domain_reader_domain,
                               self.config.client.domain_reader),
                ex_domain_admin=j(
                    self.config.client.exchange_admin_domain,
                    self.config.client.exchange_admin),
                management_server=self.config.client.management_host,
                exchange_server=self.config.client.secondary_management_host,
                session_key=self._gen_key(),
                logger=self.logger,
                host=self.config.client.jumphost,
                port=self.config.client.jumphost_port,
                ca=self.config.client.ca,
                client_key=self.config.client.client_key,
                client_cert=self.config.client.client_cert,
                check_name=self.config.client.hostname_verification,
                encrypted=self.config.client.enabled_encryption)
        except URLError as e:
            # Here, we handle the rare circumstance that the springboard is
            # down when we connect to it. We log an error so someone can
            # act upon this if it is appropriate.
            self.logger.error(
                "Can't connect to springboard! Please notify postmaster!")
            raise ServerUnavailableException(text_type(e))
        except Exception as e:
            # Get the traceback, put some tabs in front, and log it.
            tb = traceback.format_exc()
            self.logger.error("ExchangeClient failed setup:\n%s", tb)
            raise ServerUnavailableException(text_type(e))

    # We register spread:add as the event which should trigger this function
    @event_map('spread:add')
    def create_mailbox(self, event):
        """ Handle mailbox creation upon spread addition.

        :type event: Cerebrum.extlib.db_row.row
        :param event: The event returned from Change- or EventLog."""
        added_spread_code = self.ut.load_params(event)['spread']
        # An Exchange-spread has been added! Let's make a mailbox!
        if added_spread_code == self.mb_spread:
            et, eid = self.ut.get_account_owner_info(event['subject_entity'])
            uname = self.ut.get_account_name(event['subject_entity'])

            # Collect information needed to create mailbox.
            # First for accounts owned by persons
            if et == self.co.entity_person:
                first_name, last_name, full_name = self.ut.get_person_names(
                    person_id=eid)

                hide_from_address_book = (
                    not event['subject_entity'] ==
                    self.ut.get_primary_account(person_id=eid))

            # Then for accounts owned by groups
            elif et == self.co.entity_group:
                gname, desc = self.ut.get_group_information(eid)

                hide_from_address_book = False
            else:
                # An exchange-spread has been given to an account not owned
                # by a person or a group
                self.logger.warn('eid:%d: Account %s is not owned by a person '
                                 'or group. Skip.', event['event_id'], uname)
                # Raise exception, this should result in silent discard
                raise EntityTypeError

            # Create the mailbox
            try:
                self.ec.new_mailbox(uname)
                self.logger.info('eid:%d: Created new mailbox for %s',
                                 event['event_id'], uname)
                self.ut.log_event_receipt(event, 'exchange:acc_mbox_create')
            except ExchangeException as e:
                self.logger.warn('eid:%d: Failed creating mailbox for %s: %s',
                                 event['event_id'], uname, e)
                raise EventExecutionException

            # Disable the email address policy
            try:
                self.ec.set_mailbox_address_policy(uname,
                                                   enabled=False)
            except ExchangeException as e:
                self.logger.warn(
                    'eid:%d: Failed disabling address policy for %s',
                    event['event_id'], uname)
                self.ut.log_event(event, 'exchange:set_ea_policy')
                ev_mod = event.copy()
                etid, tra, sh, hq, sq = self.ut.get_email_target_info(
                    target_entity=event['subject_entity'])
                ev_mod['subject_entity'] = etid
                self.ut.log_event(ev_mod, 'email_primary_address:add_primary')

            if not hide_from_address_book:
                try:
                    self.ec.set_mailbox_visibility(
                        uname, visible=True)
                    self.logger.info(
                        'eid:%d: Publishing %s in address book...',
                        event['event_id'], uname)
                    # TODO: Mangle the event som it represents this correctly??
                    self.ut.log_event_receipt(event, 'exchange:per_e_reserv')
                except ExchangeException as e:
                    self.logger.warn(
                        'eid:%d: Could not publish %s in address book',
                        event['event_id'], uname)
                    self.ut.log_event(event, 'trait:add')

            # Collect'n set valid addresses for the mailbox
            addrs = self.ut.get_account_mailaddrs(event['subject_entity'])
            try:
                self.ec.add_mailbox_addresses(uname, addrs)
                self.logger.info('eid:%d: Added addresses for %s',
                                 event['event_id'], uname)
                # TODO: Higher resolution? Should we do this for all addresses,
                # and mangle the event to represent this?
                self.ut.log_event_receipt(event, 'exchange:acc_addr_add')
            except ExchangeException as e:
                self.logger.warn(
                    'eid:%d: Could not add e-mail addresses for %s',
                    event['event_id'], uname)
                # Creating new events in case this fails
                mod_ev = event.copy()
                for x in addrs:
                    x = x.split('@')
                    info = self.ut.get_email_domain_info(
                        email_domain_name=x[1])
                    mod_ev['change_params'] = {'dom_id': info['id'], 'lp': x[0]}
                    etid, tra, sh, hq, sq = self.ut.get_email_target_info(
                        target_entity=event['subject_entity'])
                    mod_ev['subject_entity'] = etid
                    self.ut.log_event(mod_ev, 'email_address:add_address')

            # Set the primary mailaddress
            pri_addr = self.ut.get_account_primary_email(
                event['subject_entity'])
            try:
                self.ec.set_primary_mailbox_address(uname,
                                                    pri_addr)
                self.logger.info('eid:%d: Defined primary address for %s',
                                 event['event_id'], uname)
                self.ut.log_event_receipt(event, 'exchange:acc_primaddr')
            except ExchangeException as e:
                self.logger.warn('eid:%d: Could not set primary address on %s',
                                 event['event_id'], uname)
                # Creating a new event in case this fails
                ev_mod = event.copy()
                etid, tra, sh, hq, sq = self.ut.get_email_target_info(
                    target_entity=event['subject_entity'])
                ev_mod['subject_entity'] = etid
                self.ut.log_event(ev_mod, 'email_primary_address:add_primary')

            # Set the initial quota
            aid = self.ut.get_account_id(uname)

            et_eid, tid, tt, hq, sq = self.ut.get_email_target_info(
                target_entity=aid)
            try:
                soft = (hq * sq) / 100
                self.ec.set_mailbox_quota(uname, soft, hq)
                self.logger.info('eid:%d: Set quota (%s, %s) on %s',
                                 event['event_id'], soft, hq, uname)
            except ExchangeException as e:
                self.logger.warn('eid:%d: Could not set quota on %s: %s',
                                 event['event_id'], uname, e)
                # Log an event for setting the quota if it fails
                mod_ev = {'dest_entity': None,
                          'subject_entity': et_eid,
                          'change_params': {'soft': sq, 'hard': hq}}
                self.ut.log_event(mod_ev, 'email_quota:add_quota')

            # Generate events for addition of the account into the groups the
            # account should be a member of
            groups = self.ut.get_account_group_memberships(uname,
                                                           self.group_spread)
            for gname, gid in groups:
                faux_event = {'subject_entity': aid,
                              'dest_entity': gid,
                              'change_params': None}

                self.logger.debug1('eid:%d: Creating event: Adding %s to %s',
                                   event['event_id'], uname, gname)
                self.ut.log_event(faux_event, 'e_group:add')

            # Set forwarding address
            fwds = self.ut.get_account_forwards(aid)
            remote_fwds = list(set(fwds) - set(addrs))
            local_delivery = list(set(fwds) & set(addrs))

            if remote_fwds:
                try:
                    self.ec.set_forward(uname, remote_fwds[0])
                    self.logger.info('eid:%d: Set forward for %s to %s',
                                     event['event_id'], uname,
                                     remote_fwds[0])
                except ExchangeException as e:
                    self.logger.warn(
                        'eid:%d: Can\'t set forward for %s to %s: %s',
                        event['event_id'], uname, remote_fwds[0], e)
                    # We log an faux event, since setting the forward fails
                    # Collect email target id, and construct our payload
                    etid, tid, tt, hq, sq = self.ut.get_email_target_info(
                        target_entity=aid)
                    params = {'forward': remote_fwds[0],
                              'enable': 'T'}
                    faux_event = {'subject_entity': etid,
                                  'dest_entity': etid,
                                  'change_params': params}

                    self.logger.debug1(
                        'eid:%d: Creating event: Set forward %s on %s',
                        event['event_id'], remote_fwds[0], uname)
                    self.ut.log_event(faux_event, 'email_forward:add_forward')

            if local_delivery:
                try:
                    self.ec.set_local_delivery(uname, True)
                    self.logger.info(
                        '%s local delivery for %s',
                        'Enabled' if local_delivery else 'Disabled',
                        uname)
                except ExchangeException as e:
                    self.logger.warn(
                        "eid:%d: Can't %s local delivery for %s: %s",
                        event['event_id'],
                        'enable' if local_delivery else 'disable',
                        uname,
                        e)

                    # We log an faux event, since setting the local delivery
                    # fails Collect email target id, and construct our payload
                    etid, tid, tt, hq, sq = self.ut.get_email_target_info(
                        target_entity=aid)
                    params = {'forward': local_delivery[0],
                              'enable': 'T'}
                    faux_event = {'subject_entity': etid,
                                  'dest_entity': etid,
                                  'change_params': params}

                    self.logger.debug1(
                        'eid:%d: Creating event: Set local delivery on %s',
                        event['event_id'], uname)
                    self.ut.log_event(faux_event, 'email_forward:add_forward')

        # If we wind up here, the spread type is notrelated to our target
        # system
        else:
            raise UnrelatedEvent

    @event_map('trait:add', 'trait:mod', 'trait:del', 'e_group:add',
               'e_group:rem')
    def set_address_book_visibility(self, event):
        """Set the visibility of a persons accounts in the address book.

        The primary accounts visibility is determined by consulting the
        following sources, in order:

        1. If the owning person is a member of the
           randzone exclusion group, the primary account will always be shown.
        2. The reserve_public trait on the person.

        If any of the settings fail to be proceessed, the event will be
        re-tried later on.

        :type event: Cerebrum.extlib.db_row.row
        :param event: The event returned from Change- or EventLog

        :raises ExchangeException: If all accounts could not be updated.
        """
        # TODO: This function operates on multiple accounts in Exchange. Should
        # we split the event in an agent, somewhere, so we generate an event
        # for each account? There are both pros and cons to this approch.

        # Check if the entity we target with this event is a person. If it is
        # not, we throw away the event.
        try:
            et = self.ut.get_entity_type(event['subject_entity'])
            if not et == self.co.entity_person:
                raise Errors.NotFoundError
        except Errors.NotFoundError:
            raise EntityTypeError

        params = self.ut.load_params(event)

        # Extract event-type for readability
        ev_type = event['event_type']
        # Handle group additions
        if ev_type in (self.co.group_add, self.co.group_rem,):
            # Check if this group addition operation is related to
            # the randzone group. If not, raise the UnrelatedEvent exception.
            # If it is related to randzones, and the person is a member of the
            # randzone group, show the person in the address list. If the
            # person has been removed from the randzone group, load the state
            # from the database.

            member_of = self.ut.get_parent_groups(event['dest_entity'])
            if self.randzone_unreserve_group not in member_of:
                raise UnrelatedEvent
            else:
                if (self.randzone_unreserve_group in
                        self.ut.get_person_membership_groupnames(
                            event['subject_entity'])):
                    hidden_from_address_book = False
                else:
                    hidden_from_address_book = (
                        not event['subject_entity'] ==
                        self.ut.get_primary_account(
                            person_id=event['subject_entity']))
        # Handle trait settings
        else:
            # Check if this is a reservation-related trait operation. If it is
            # not, we raise the UnrelatedEvent exception since we don't have
            # anything to do. If it is a reservation-related trait, load the
            # reservation status from the database.
            if params['code'] != self.co.trait_public_reservation:
                raise UnrelatedEvent
            else:
                hidden_from_address_book = (
                    not event['subject_entity'] ==
                    self.ut.get_primary_account(
                        person_id=event['subject_entity']))

        # Utility function for setting visibility on accounts in Exchange.
        def _set_visibility(uname, vis):
            state = 'Hiding' if vis else 'Publishing'
            fail_state = 'hide' if vis else 'publish'
            try:
                # We do a not-operation here, since the
                # set_mailbox_visibility-methods logic about wheter an account
                # should be hidden or not, is inverse in regards to what we do
                # above :S
                self.ec.set_mailbox_visibility(uname, not vis)
                self.logger.info('eid:%d: %s %s in address book..',
                                 event['event_id'],
                                 state,
                                 uname)
                return True
            except ExchangeException as e:
                self.logger.warn("eid:%d: Can't %s %s in address book: %s",
                                 event['event_id'],
                                 fail_state,
                                 uname,
                                 e)
                return False

        # Parameter used to decide if any calls to Exchange fails. In order to
        # ensure correct state (this is imperative in regards to visibility),
        # we must always raise EventExecutionException in case one (or more) of
        # the calls fail).
        no_fail = True

        # Fetch the primary accounts entity_id
        primary_account_id = self.ut.get_primary_account(
            event['subject_entity'])

        # Loop trough all the persons accounts, and set the appropriate
        # visibility state for them.
        for aid, uname in self.ut.get_person_accounts(event['subject_entity'],
                                                      self.mb_spread):
            # Set the state we deduced earlier on the primary account.
            if aid == primary_account_id:
                tmp_no_fail = _set_visibility(uname, hidden_from_address_book)
            # Unprimary-accounts should never be shown in the address book.
            else:
                tmp_no_fail = _set_visibility(uname, True)
            # Save the potential failure-state
            if not tmp_no_fail:
                no_fail = False

        # Raise EventExecutionException, if any of the calls to Exchange
        # has failed.
        if not no_fail:
            raise EventExecutionException

        # Log a reciept for this change.
        self.ut.log_event_receipt(event, 'exchange:per_e_reserv')

    @event_map('exchange:set_ea_policy')
    def set_address_policy(self, event):
        """Disable the address policy on mailboxes or groups.

        @type event: Cerebrum.extlib.db_row.row
        @param event: The event returned from Change- or EventLog
        """
        try:
            et = self.ut.get_entity_type(event['subject_entity'])
            if not et == self.co.entity_person:
                raise Errors.NotFoundError
            # If we can't find a person with this entity id, we silently
            # discard the event by doing nothing
        except Errors.NotFoundError:
            raise EntityTypeError

        if et == self.co.entity_account:
            name = self.ut.get_account_name(event['subject_entity'])
            try:
                self.ec.set_mailbox_address_policy(name)
                self.logger.info('eid:%d: EAP disabled on %s',
                                 event['event_id'], name)
            except ExchangeException, e:
                self.logger.warn(
                    'eid:%d: Can\'t disable EAP on account %s: %s',
                    event['event_id'], name, e)
                raise EventExecutionException
        elif et == self.co.entity_group:
            name, desc = self.ut.get_group_information(event['subject_entity'])
            try:
                self.ec.set_distgroup_address_policy(name)
                self.logger.info('eid:%d: EAP disabled on %s',
                                 event['event_id'], name)
            except ExchangeException, e:
                self.logger.warn('eid:%d: Can\'t disable EAP for %s: %s',
                                 event['event_id'], name, e)
        else:
            raise UnrelatedEvent
