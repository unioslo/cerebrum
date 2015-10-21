#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2015 University of Oslo, Norway
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

import cereconf
import cerebrum_path
getattr(cereconf, "linter", "should not nag")
getattr(cerebrum_path, "linter", "should not nag")

import multiprocessing
import os
import pickle
import time
import traceback

from urllib2 import URLError

from Queue import Empty

from Cerebrum.modules.exchange.Exceptions import (ExchangeException,
                                                  ServerUnavailableException,
                                                  AlreadyPerformedException)
from Cerebrum.modules.event.EventExceptions import (EventExecutionException,
                                                    EventHandlerNotImplemented,
                                                    EntityTypeError,
                                                    UnrelatedEvent)
from Cerebrum.modules.event.EventDecorator import EventDecorator
from Cerebrum.modules.event.HackedLogger import Logger
from Cerebrum.modules.exchange.CerebrumUtils import CerebrumUtils
from Cerebrum.Utils import Factory
from Cerebrum import Errors


class ExchangeEventHandler(multiprocessing.Process):
    """Event handler for Exchange.

    This event handler is started by the event daemon.
    It implements functions that are called based on wich ChangeTypes they are
    associated with, trough the EventDecorator.RegisterHandler decorator.
    """

    # Event to method lookup table. Populated by decorators.
    _lut_type2meth = {}

    def __init__(self, config, event_queue, logger_queue, run_state, mock):
        """ExchangeEventHandler initialization routine.

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
        self.event_queue = event_queue
        self.run_state = run_state
        self.config = config
        # TODO: This is a hack. Fix it
        self.logger_queue = logger_queue
        self.logger = Logger(self.logger_queue)
        self.mock = mock

        super(ExchangeEventHandler, self).__init__()
        self.logger.debug("Hello from event handler class %s", self.__class__)

    def _post_fork_init(self):
        r"""Post-fork init method.

        We need to initialize the database-connection after we fork,
        or else we will get random errors since all the threads share
        the same sockets.. This is somewhat documented here:
        http://www.postgresql.org/docs/current/static/libpq-connect.html \
                #LIBPQ-CONNECT

        We also initialize the ExchangeClient here.. We can start faster
        when we do it in paralell.
        """
        # fhl said I shoul rather use the PID or something truly unique here.
        # That sounds acceptable.
        gen_key = lambda: 'CB%s' % hex(os.getpid())[2:].upper()
        self.key = gen_key

        # Try to connect to Exchange.
        # We do this in a loop, since if we connect while the springboard is
        # down, we need to re-try connecting. Also, the while depens on the run
        # state, so we will shut down if we are signaled to do so.
        self.ec = None

        if self.mock:
            self.logger.info('Running in mock-mode')
            from Cerebrum.modules.exchange.v2013.ExchangeClient import (
                ClientMock as ExchangeClient, )
        else:
            from Cerebrum.modules.exchange.v2013.ExchangeClient import (
                ExchangeClient, )
        self.logger.debug("EventHandler post fork")

        i = 0
        while self.run_state.value:
            i = i + 1
            self.logger.debug("Trying to connect to springboard (%d)", i)
            try:
                self.ec = ExchangeClient(
                    auth_user=self.config['auth_user'],
                    domain_admin=self.config['domain_admin'],
                    ex_domain_admin=self.config['ex_domain_admin'],
                    management_server=self.config['management_server'],
                    exchange_commands=self.config.get('exchange_commands'),
                    session_key=gen_key(),
                    logger=self.logger,
                    host=self.config['server'],
                    port=self.config['port'],
                    ca=self.config.get('ca'),
                    client_key=self.config.get('client_key'),
                    client_cert=self.config.get('client_cert'),
                    check_name=self.config.get('check_name', True),
                    encrypted=self.config['encrypted'])
            except URLError:
                # Here, we handle the rare circumstance that the springboard is
                # down when we connect to it. We log an error so someone can
                # act upon this if it is appropriate.
                self.logger.error(
                    "Can't connect to springboard! Please notify postmaster!")
                # If we shut down, we don't want to wait X minutes :)
                if self.run_state.value:
                    time.sleep(3*60)
            else:
                break
        self.logger.debug("Connected to springboard")

        # Initialize the Database and Constants object
        self.db = Factory.get('Database')(client_encoding='UTF-8')
        self.co = Factory.get('Constants')(self.db)

        # Spreads to use!
        self.mb_spread = self.co.Spread(self.config['mailbox_spread'])
        self.group_spread = self.co.Spread(self.config['group_spread'])
        self.ad_spread = self.co.Spread(self.config['ad_spread'])

        # Group lookup patterns
        self.group_name_translation = self.config['group_name_translation']
        # Group defining that rendzone users should be shown in address book
        self.randzone_unreserve_group = self.config['randzone_unreserve_group']

        # Throw away our implicit transaction after fetching spreads
        self.db.rollback()

        # Initialise the Utils. This contains functions to pull data from
        # Cerebrum
        self.ut = CerebrumUtils()

    def run(self):
        """Main event-multiprocessing loop.

        Spawned by multiprocessing.Process.__init__
        """
        # When we execute code here, we have forked. We can now initialize
        # the database (and more)
        self._post_fork_init()

        # It is a bit ugly to directly access a multiprocessing.Value object
        # like this, but it is simple and it works. Doing something like
        # this with more "pythonic" types adds a lot of complexity.
        self.logger.info('Listening for events')
        while self.run_state.value:
            # Collect a new event.
            try:
                raw_ev = self.event_queue.get(block=True, timeout=5)
                ev = raw_ev['event']
            except Empty:
                # We continue here, since the queue will be empty
                # at times.
                continue
            self.logger.debug3('Got a new event: %s' % str(ev))

            # Try to lock the event
            try:
                self.db.lock_event(ev['event_id'])
                # We must commit to lock the event.
                self.db.commit()
            except Errors.NotFoundError:
                # We should normally not end up here.
                # We _might_ end up here, when the
                # DelayedNotificationCollector is running.
                # We'll just move along silently...
                self.logger.debug3('Event already processed: %s' % str(ev))
                self.db.rollback()
                continue

            # We try to handle the event
            try:
                self.handle_event(ev)
                # When the command(s) have run sucessfully, we remove the
                # the triggering event.
                try:
                    self.db.remove_event(ev['event_id'])
                except Errors.NotFoundError:
                    self.logger.debug3(
                        'Event deleted while multiprocessing: %s' %
                        str(ev))
                    self.db.commit()
                    continue

                # TODO: Store the receipt in ChangeLog! We need to handle
                # EntityTypeError and UnrelatedEvent in a appropriate manner
                # for this to work. Now we always store the reciept in the
                # functions called. That is a tad innapropriate, but also
                # correct. Hard choices.
                self.db.commit()
            # If an event fails, we just release it, and let the
            # DelayedNotificationCollector enqueue it when appropriate
            except EventExecutionException, e:
                self.logger.debug('Failed to process event %d: %s' %
                                  (ev['event_id'], str(e)))
                try:
                    self.db.release_event(ev['event_id'])
                except Errors.NotFoundError:
                    # In this case, the event has been deleted while running,
                    # therefore, we cannot release it.
                    # TODO: Implement something that will lock events for
                    # deletion while they are beeing processed. If that is
                    # implemented, this could be removed.
                    self.db.rollback()
                else:
                    self.db.commit()
            except EventHandlerNotImplemented:
                self.logger.debug3('Event Handler Not Implemented!')
                # We remove the event for now.. Or else it will just
                # sit around for a loooong time...
                self.db.remove_event(ev['event_id'])
                self.db.commit()
#            except (EntityTypeError, UnrelatedEvent):
#                # When this gets raised, the owner type of the object
#                # is probably wrong. We silently discard the event
#                self.db.remove_event(ev['event_id'])
#                self.db.commit()
            except Exception, e:
                # If we wind up here, we have found a "state" that the
                # programmer failed to imagine. We log it, so we can process
                # further events, and shut down the event dæmon gracefully
                # (some systems don't like hard kills, like WinRM / Powershell,
                # which has natzi rules on connection counts and so forth)
                #
                # We don't release the "lock" on the event, since the event
                # will probably fail the next time around. Manual intervention
                # IS therefore REQUIRED!
                #
                # Get the traceback, put some tabs in front, and log it.
                tb = traceback.format_exc()
                tb = '\t' + tb.replace('\n', '\t\n')
                self.logger.error(
                    'Oops! Didn\'t see that one coming! :)\n%s\n%s' %
                    (str(ev), tb))
#                # We unlock the event, so it can be retried
#                try:
#                    self.db.release_event(ev['event_id'])
#                except Errors.NotFoundError:
#                    self.db.rollback()
#                else:
#                    self.db.commit()

        # When the run-state has been set to 0, we kill the pssession
        # We check for existance, before tearing down the connection, in the
        # rare case that we shut down without having established a connection,
        # we'll get a crash if we don't do this.
        if self.ec:
            self.ec.kill_session()
            self.ec.close()
        self.logger.info('ExchangeEventHandler stopped')

    def handle_event(self, event):
        """Call the appropriate handlers."""
        # TODO: try/except this?
        key = str(self.co.ChangeType(event['event_type']))
        self.logger.debug3('Got event key: %s' % key)
        try:
            cmds = ExchangeEventHandler._lut_type2meth[key]
        except KeyError:
            raise EventHandlerNotImplemented

        # Call the appropriate handler(s)
        # TODO: Think about what happens if one of the commands fail,
        # if that happens, the event will be requeued, and the next
        # time it runs, it will crash again since (for example) a
        # mailbox already exists when it tries to create a new one.
        # We might escape this ugly state by defining EventTypes,
        # just like we define ChangeTypes. Needs some thought.
        for cmd in cmds:
            try:
                cmd(self, event)
            except (EntityTypeError, UnrelatedEvent):
                pass

#######################
# Event handler methods
#######################
# Event handler methods are decorated with a decorator, which takes change
# types as arguments. The decorator populates a LUT upon class definition,
# which is consulted in order to find out which change types trigger which
# methods. Please remember to decorate your methods in a sane manner! ;)

######
# Mailbox related commands
######
# TODO: What about name changes?

    # We register spread:add as the event which should trigger this function
    @EventDecorator.RegisterHandler('spread:add')
    def create_mailbox(self, event):
        """ Handle mailbox creation upon spread addition.

        :type event: Cerebrum.extlib.db_row.row
        :param event: The event returned from Change- or EventLog."""
        # TODO: Handle exceptions!
        # TODO: What if the mailbox allready exists?
        added_spread_code = self.ut.unpickle_event_params(event)['spread']
        # An Exchange-spread has been added! Let's make a mailbox!
        # TODO: Check for subject entity type? It is supposed to be an account
        #           Explicit instead of implicit
        if added_spread_code == self.mb_spread:
            et, eid = self.ut.get_account_owner_info(event['subject_entity'])
            uname = self.ut.get_account_name(event['subject_entity'])

            # Collect information needed to create mailbox.
            # First for accounts owned by persons
            if et == self.co.entity_person:
                firstname, lastname, fullname = self.ut.get_person_names(
                    person_id=eid)

                hide_from_address_book = (
                    self.ut.is_electronic_reserved(person_id=eid) or
                    not event['subject_entity'] ==
                    self.ut.get_primary_account(person_id=eid))

            # Then for accounts owned by groups
            elif et == self.co.entity_group:
                gname, desc = self.ut.get_group_information(eid)
                firstname, lastname, fullname = self.ut.construct_group_names(
                    uname, gname)
                # TODO: Is this ok?
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
                self.ec.new_mailbox(uname, fullname,
                                    firstname, lastname,
                                    ou=self.config['mailbox_path'])
                self.logger.info('eid:%d: Created new mailbox for %s' %
                                 (event['event_id'], uname))
                # TODO: Should we log a receipt for hiding the mbox in the
                # address book? We don't really need to, since everyone is
                # hidden by default.
                self.ut.log_event_receipt(event, 'exchange:acc_mbox_create')
            except (ExchangeException, ServerUnavailableException), e:
                self.logger.warn('eid:%d: Failed creating mailbox for %s: %s' %
                                 (event['event_id'], uname, e))
                raise EventExecutionException

            if not hide_from_address_book:
                try:
                    self.ec.set_mailbox_visibility(
                        uname, visible=True)
                    self.logger.info(
                        'eid:%d: Publishing %s in address book...' %
                        (event['event_id'], uname))
                    # TODO: Mangle the event som it represents this correctly??
                    self.ut.log_event_receipt(event, 'exchange:per_e_reserv')
                except (ExchangeException, ServerUnavailableException), e:
                    self.logger.warn(
                        'eid:%d: Could not publish %s in address book' %
                        (event['event_id'], uname))
                    self.ut.log_event(event, 'trait:add')

            # Collect'n set valid addresses for the mailbox
            addrs = self.ut.get_account_mailaddrs(event['subject_entity'])
            try:
                self.ec.add_mailbox_addresses(uname, addrs)
                self.logger.info('eid:%d: Added addresses for %s' %
                                 (event['event_id'], uname))
                # TODO: Higher resolution? Should we do this for all addresses,
                # and mangle the event to represent this?
                self.ut.log_event_receipt(event, 'exchange:acc_addr_add')
            except (ExchangeException, ServerUnavailableException), e:
                self.logger.warn(
                    'eid:%d: Could not add e-mail addresses for %s' %
                    (event['event_id'], uname))
                # Creating new events in case this fails
                mod_ev = event.copy()
                for x in addrs:
                    x = x.split('@')
                    info = self.ut.get_email_domain_info(
                        email_domain_name=x[1])
                    mod_ev['change_params'] = pickle.dumps(
                        {'dom_id': info['id'], 'lp': x[0]})
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
                self.logger.info('eid:%d: Defined primary address for %s' %
                                 (event['event_id'], uname))
                self.ut.log_event_receipt(event, 'exchange:acc_primaddr')

            except (ExchangeException, ServerUnavailableException), e:
                self.logger.warn('eid:%d: Could not set primary address on %s'
                                 % (event['event_id'], uname))
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
                self.logger.info('eid:%d: Set quota (%s, %s) on %s' %
                                 (event['event_id'], soft, hq, uname))
            except (ExchangeException, ServerUnavailableException), e:
                self.logger.warn('eid:%d: Could not set quota on %s: %s' %
                                 (event['event_id'], uname, e))
                # Log an event for setting the quota if it fails
                mod_ev = {'dest_entity': None, 'subject_entity': et_eid}
                mod_ev['change_params'] = pickle.dumps(
                    {'soft': sq, 'hard': hq})
                self.ut.log_event(mod_ev, 'email_quota:add_quota')

            # Generate events for addition of the account into the groups the
            # account should be a member of
            groups = self.ut.get_account_group_memberships(uname,
                                                           self.group_spread)
            for gname, gid in groups:
                faux_event = {'subject_entity': aid,
                              'dest_entity': gid,
                              'change_params': pickle.dumps(None)}

                self.logger.debug1('eid:%d: Creating event: Adding %s to %s' %
                                   (event['event_id'], uname, gname))
                self.ut.log_event(faux_event, 'e_group:add')

            # Set forwarding address
            fwds = self.ut.get_account_forwards(aid)
            remote_fwds = list(set(fwds) - set(addrs))
            local_delivery = list(set(fwds) & set(addrs))

            if remote_fwds:
                try:
                    self.ec.set_forward(uname, remote_fwds[0])
                    self.logger.info('eid:%d: Set forward for %s to %s' %
                                     (event['event_id'], uname,
                                      remote_fwds[0]))
                    # TODO: Log reciept
                except (ExchangeException, ServerUnavailableException), e:
                    self.logger.warn(
                        'eid:%d: Can\'t set forward for %s to %s: %s' %
                        (event['event_id'], uname, str(remote_fwds[0]), e))
                    # We log an faux event, since setting the forward fails
                    # Collect email target id, and construct our payload
                    etid, tid, tt, hq, sq = self.ut.get_email_target_info(
                        target_entity=aid)
                    params = {'forward': remote_fwds[0],
                              'enable': 'T'}
                    faux_event = {'subject_entity': etid,
                                  'dest_entity': etid,
                                  'change_params': pickle.dumps(params)}

                    self.logger.debug1(
                        'eid:%d: Creating event: Set forward %s on %s' %
                        (event['event_id'], remote_fwds[0], uname))
                    self.ut.log_event(faux_event, 'email_forward:add_forward')

            if local_delivery:
                try:
                    self.ec.set_local_delivery(uname, True)
                    # TODO: RECIEPT?
                    self.logger.info(
                        '%s local delivery for %s' % (
                            'Enabled' if local_delivery else 'Disabled',
                            uname))
                except (ExchangeException, ServerUnavailableException), e:
                    self.logger.warn(
                        "eid:%d: Can't %s local delivery for %s: %s" % (
                            event['event_id'],
                            'enable' if local_delivery else 'disable',
                            uname,
                            e))

                    # We log an faux event, since setting the local delivery
                    # fails Collect email target id, and construct our payload
                    etid, tid, tt, hq, sq = self.ut.get_email_target_info(
                        target_entity=aid)
                    params = {'forward': local_delivery[0],
                              'enable': 'T'}
                    faux_event = {'subject_entity': etid,
                                  'dest_entity': etid,
                                  'change_params': pickle.dumps(params)}

                    self.logger.debug1(
                        'eid:%d: Creating event: Set local delivery on %s' %
                        (event['event_id'], uname))
                    self.ut.log_event(faux_event, 'email_forward:add_forward')

        # If we wind up here, the spread type is notrelated to our target
        # system
        else:
            raise UnrelatedEvent

    @EventDecorator.RegisterHandler(['spread:delete'])
    def remove_mailbox(self, event):
        """Event handler for removal of mailbox when an account looses its
        spread.

        :type event: Cerebrum.extlib.db_row.row
        :param event: The event returned from Change- or EventLog."""
        removed_spread_code = self.ut.unpickle_event_params(event)['spread']
        if removed_spread_code == self.mb_spread:
            # TODO: This is highly temporary! Remove the following line when
            #       we have solved archiving of mailboxes ;)
            raise EventExecutionException
            uname = self.ut.get_account_name(event['subject_entity'])
            try:
                self.ec.remove_mailbox(uname)
                self.logger.info(
                    'eid:{event_id}: Removed mailbox {uname}'.format(
                        event_id=event['event_id'],
                        uname=uname))
                # Log a reciept that represents completion of the operation in
                # ChangeLog.
                # TODO: Move this to the caller sometime
                self.ut.log_event_receipt(event, 'exchange:acc_mbox_delete')
            except (ExchangeException, ServerUnavailableException) as e:
                self.logger.warn(
                    'eid:{event_id}: Couldn\'t remove mailbox for {uname}'
                    ' {error}'.format(event_id=event['event_id'],
                                      uname=uname,
                                      error=e))
                raise EventExecutionException

    @EventDecorator.RegisterHandler(['person:name_add', 'person:name_del',
                                     'person:name_mod'])
    def set_names(self, event):
        """Event handler method used for updating a persons accounts with
        the persons new name.

        :type event: Cerebrum.extlib.db_row.row
        :param event: The event returned from Change- or EventLog

        :raises ExchangeException: If all accounts could not be updated.
        """
        try:
            first, last, full = self.ut.get_person_names(
                person_id=event['subject_entity'])
        except Errors.NotFoundError:
            # If we arrive here, the person has probably been deleted,
            # and we can't look her up!
            raise UnrelatedEvent

        for aid, uname in self.ut.get_person_accounts(
                spread=self.mb_spread,
                person_id=event['subject_entity']):
            if self.mb_spread in self.ut.get_account_spreads(aid):
                try:
                    self.ec.set_mailbox_names(uname, first, last, full)
                    self.logger.info(
                        'eid:{event_id}: Updated name for {uname}'.format(
                            event_id=event['event_id'], uname=uname))
                except (ExchangeException, ServerUnavailableException) as e:
                    self.logger.warn(
                        'eid:{event_id}: Failed updating name for {uname}: '
                        '{error}'.format(event_id=event['event_id'],
                                         uname=uname, error=e))
                    raise EventExecutionException
            else:
                # If we wind up here, the user is not supposed to be in
                # Exchange :S
                raise UnrelatedEvent

    # Utility function for setting visibility on accounts in Exchange.
    def _set_visibility(self, event, uname, vis):
        state = 'Hiding' if vis else 'Publishing'
        fail_state = 'hide' if vis else 'publish'
        try:
            # We do a not-operation here, since the
            # set_mailbox_visibility-methods logic about wheter an account
            # should be hidden or not, is inverse in regards to what we do
            # above :S
            self.ec.set_mailbox_visibility(uname, not vis)
            self.logger.info('eid:%d: %s %s in address book..' %
                             (event['event_id'],
                              state,
                              uname))
            return True
        except (ExchangeException, ServerUnavailableException), e:
            self.logger.warn("eid:%d: Can't %s %s in address book: %s" %
                             (event['event_id'],
                              fail_state,
                              uname,
                              e))
            return False

    @EventDecorator.RegisterHandler(['trait:add', 'trait:mod', 'trait:del',
                                     'e_group:add', 'e_group:rem'])
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
            params = self.ut.unpickle_event_params(event)
            if not et == self.co.entity_person:
                raise Errors.NotFoundError
        except Errors.NotFoundError:
            raise EntityTypeError

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
                    hidden_from_address_book = self.ut.is_electronic_reserved(
                        person_id=event['subject_entity'])
        # Handle trait settings
        else:
            # Check if this is a reservation-related trait operation. If it is
            # not, we raise the UnrelatedEvent exception since we don't have
            # anything to do. If it is a reservation-related trait, load the
            # reservation status from the database.
            if params['code'] != self.co.trait_public_reservation:
                raise UnrelatedEvent
            else:
                hidden_from_address_book = self.ut.is_electronic_reserved(
                    person_id=event['subject_entity'])

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
        accounts = self.ut.get_person_accounts(event['subject_entity'],
                                               self.mb_spread)
        for aid, uname in accounts:
            # Set the state we deduced earlier on the primary account.
            if aid == primary_account_id:
                tmp_no_fail = self._set_visibility(event,
                                                   uname,
                                                   hidden_from_address_book)
            # Unprimary-accounts should never be shown in the address book.
            else:
                tmp_no_fail = self._set_visibility(event, uname, True)
            # Save the potential failure-state
            if not tmp_no_fail:
                no_fail = False

        # Raise EventExecutionException, if any of the calls to Exchange
        # has failed.
        if not no_fail:
            raise EventExecutionException

        # Alter change params and entity id of subject. Log changes for all
        # affected accounts.
        for aid, _ in accounts:
            recpt = {'subject_entity': aid,
                     'dest_entity': None,
                     'change_params': pickle.dumps(
                         {'visible': (aid == primary_account_id and
                                      not hidden_from_address_book)})}
            self.ut.log_event_receipt(recpt, 'exchange:per_e_reserv')

    @EventDecorator.RegisterHandler(['ac_type:add',
                                     'ac_type:mod',
                                     'ac_type:del'])
    def set_address_book_visibility_for_primary_account_change(self, event):
        """Update address book visibility when primary account changes.

        :param event: The event returned from Change- or EventLog.
        :type event: Cerebrum.extlib.db_row.row
        :raises ExchangeException: If the visibility can't be set because of an
            Exchange related error.
        :raises EventExecutionException: If the event could not be processed
            properly."""
        # TODO: This should be re-written as an aggregate-enrich-split-agent,
        # and a much simpler handler.
        # TODO: Add some criterias that filter out events that does not result
        # in primary-user change?

        # Get information about the accounts owner
        owner_type, owner_id = self.ut.get_account_owner_info(
            event['subject_entity'])

        # We'll only handle accounts that are owned by persons
        if owner_type != self.co.entity_person:
            raise UnrelatedEvent

        # Fetch primary account id
        new_primary_id = self.ut.get_primary_account(owner_id)

        # Collect reservation-status for primary account.
        is_reserved = (self.randzone_unreserve_group not in
                       self.ut.get_person_membership_groupnames(owner_id) and
                       self.ut.is_electronic_reserved(owner_id))

        # Store success-state
        no_fail = True

        # Update visibility of the persons accounts
        accounts = self.ut.get_person_accounts(owner_id, self.mb_spread)
        for aid, uname in accounts:
            if aid == new_primary_id and not is_reserved:
                no_fail = no_fail and self._set_visibility(
                    event, uname, is_reserved)
            else:
                no_fail = no_fail and self._set_visibility(
                    event, uname, True)  # True means hide.

        # Raise an exception to re-handle the event later, if some of them
        # fails. We choose to do this after trying to set visibility on all
        # accounts, so we are a bit more sure that we won't accidentally
        # expose someone in the address book.
        if not no_fail:
            raise EventExecutionException

        # Alter change params and entity id of subject. Log changes for all
        # affected accounts.
        for aid, _ in accounts:
            rcpt = {'subject_entity': aid,
                    'dest_entity': None,
                    'change_params': pickle.dumps(
                        {'visible': (aid == new_primary_id and
                                     not is_reserved)})}
            self.ut.log_event_receipt(rcpt, 'exchange:per_e_reserv')

    @EventDecorator.RegisterHandler(['email_quota:add_quota',
                                     'email_quota:mod_quota',
                                     'email_quota:rem_quota'])
    def set_mailbox_quota(self, event):
        """Set quota on a mailbox.

        :param event: The event returned from Change- or EventLog.
        :type event: Cerebrum.extlib.db_row.row
        :raises ExchangeException: If the forward can't be set because of an
            Exchange related error.
        :raises EventExecutionException: If the event could not be processed
            properly."""
        # TODO: Should we error check the reutrn from this method? Typewise
        # that is
        try:
            et_eid, tid, tet, hq, sq = self.ut.get_email_target_info(
                target_id=event['subject_entity'])
        except Errors.NotFoundError:
            # If we wind up here, we have recieved an event that is triggered
            # by entity:del or something. Is this a bug, or a feature? We'll
            # just define this event as unrelated.
            raise UnrelatedEvent

        # params = self.ut.unpickle_event_params(event)
        name = self.ut.get_account_name(tid)
        if self.mb_spread not in self.ut.get_account_spreads(tid):
            # If we wind up here, the user is not supposed to be in Exchange :S
            raise UnrelatedEvent
        try:
            # Unordered events facilitates the need to use the values from
            # storage.
            # hard = params['hard']
            # soft = (params['hard'] * params['soft']) / 100
            soft = (hq * sq) / 100
            hard = hq

            self.ec.set_mailbox_quota(name, soft, hard)
            self.logger.info(
                'eid:%d: Set quota (%d hard, %d soft) on mailbox for %s' %
                (event['event_id'], hard, soft, name))
        except (ExchangeException, ServerUnavailableException), e:
            self.logger.warn(
                'eid:%d: Can\'t set quota (%d hard, %d soft) for %s: %s)' %
                (event['event_id'], hard, soft, name, e))
            raise EventExecutionException

    @EventDecorator.RegisterHandler(['email_forward:add_forward',
                                     'email_forward:rem_forward',
                                     'email_forward:enable_forward',
                                     'email_forward:disable_forward'])
    def set_mailbox_forward_addr(self, event):
        """Event handler method used for handling setting of forward adresses.

        :param event: The event returned from Change- or EventLog.
        :type event: Cerebrum.extlib.db_row.row
        :raises ExchangeException: If the forward can't be set because of an
            Exchange related error.
        :raises EventExecutionException: If the event could not be processed
            properly."""
        params = self.ut.unpickle_event_params(event)

        et_eid, tid, tet, hq, sq = self.ut.get_email_target_info(
            target_id=event['subject_entity'])
        if (tet == self.co.entity_account and
                self.mb_spread in self.ut.get_account_spreads(tid)):
            uname = self.ut.get_account_name(tid)
        else:
            # Skip all email targets that are not associated with an account
            raise UnrelatedEvent

        # If the adresses is an address that is associated with the email
        # target, we throw the event away, since it is a local delivery
        # setting that will be handled by another function.
        if params['forward'] in self.ut.get_account_mailaddrs(tid):
            raise UnrelatedEvent

        address = None
        if event['event_type'] in (self.co.email_forward_enable,
                                   self.co.email_forward_add):
            address = params['forward']

        try:
            self.ec.set_forward(uname, address)
            self.logger.info('Set forward for %s to %s' % (uname, address))
        except (ExchangeException, ServerUnavailableException), e:
            self.logger.warn(
                'eid:%d: Can\'t set forward for %s to %s: %s' %
                (event['event_id'], uname, str(address), e))
            raise EventExecutionException

    @EventDecorator.RegisterHandler(['email_forward:add_forward',
                                     'email_forward:rem_forward',
                                     'email_forward:enable_forward',
                                     'email_forward:disable_forward'])
    def set_local_delivery(self, event):
        """Event handler method that sets the DeliverToMailboxAndForward option.

        :param event: The EventLog entry to process.
        :type event: Cerebrum.extlib.db_row.row
        :raises ExchangeException: If the forward can't be set because of an
            Exchange related error.
        :raises EventExecutionException: If the event could not be processed
            properly."""
        et_eid, tid, tet, hq, sq = self.ut.get_email_target_info(
            target_id=event['subject_entity'])
        if (tet == self.co.entity_account and
                self.mb_spread in self.ut.get_account_spreads(tid)):
            uname = self.ut.get_account_name(tid)
        else:
            # Skip all targets that are not account-related
            raise UnrelatedEvent

        params = self.ut.unpickle_event_params(event)
        addrs = self.ut.get_account_mailaddrs(tid)

        if ('forward' in params and 'enable' in params and
                params['forward'] in addrs and params['enable'] == 'T'):
            local_delivery = True
        elif ('forward' in params and params['forward'] in addrs and
                'enable' not in params):
            local_delivery = False
        else:
            raise UnrelatedEvent

        try:
            self.ec.set_local_delivery(uname, local_delivery)
            # TODO: RECIEPT?
            self.logger.info(
                '%s local delivery for %s' % (
                    'Enabled' if local_delivery else 'Disabled',
                    uname))
        except (ExchangeException, ServerUnavailableException), e:
            self.logger.warn(
                "eid:%d: Can't %s local delivery for %s: %s" % (
                    event['event_id'],
                    'enable' if local_delivery else 'disable',
                    uname,
                    e))
            raise EventExecutionException


# TODO: Are these so "generic"?
####
# Generic functions
####
    @EventDecorator.RegisterHandler(['email_address:add_address'])
    def add_address(self, event):
        """Event handler method used for adding e-mail addresses to
        accounts and distribution groups.

        :type event: Cerebrum.extlib.db_row.row
        :param event: The event returned from Change- or EventLog.

        :raises ExchangeException: If all accounts could not be updated."""
        params = self.ut.unpickle_event_params(event)
        domain = self.ut.get_email_domain_info(params['dom_id'])['name']
        address = '%s@%s' % (params['lp'], domain)

        try:
            et_eid, eid, eit, hq, sq = self.ut.get_email_target_info(
                target_id=event['subject_entity'])
        except Errors.NotFoundError:
            # If we wind up here, we have recieved an event that is triggered
            # by entity:del or something. Is this a bug, or a feature? We'll
            # just define this event as unrelated.
            raise UnrelatedEvent

        # Check if we are handling an account
        if eit == self.co.entity_account:
            if self.mb_spread not in self.ut.get_account_spreads(eid):
                # If we wind up here, the user is not supposed to be in
                # Exchange :S
                raise UnrelatedEvent
            uname = self.ut.get_account_name(eid)
            try:
                self.ec.add_mailbox_addresses(uname, [address])
                self.logger.info('eid:%d: Added %s to %s' %
                                 (event['event_id'], address, uname))

                # Log a reciept that represents completion of the operation in
                # ChangeLog.
                # TODO: Move this to the caller sometime
                self.ut.log_event_receipt(event, 'exchange:acc_addr_add')
            except (ExchangeException, ServerUnavailableException), e:
                self.logger.warn('eid:%d: Can\'t add %s to %s: %s' %
                                 (event['event_id'], address, uname, e))
                raise EventExecutionException

        elif eit == self.co.entity_group:
            group_spreads = self.ut.get_group_spreads(eid)
            # TODO: Do we need this? Could this happen?
            if self.group_spread in group_spreads:
                gname, desc = self.ut.get_group_information(eid)
                try:
                    self.ec.add_distgroup_addresses(gname, [address])
                    self.logger.info(
                        'eid:%d: Added %s to %s' %
                        (event['event_id'], address, gname))
                    # Log a reciept that represents completion of the operation
                    # in ChangeLog.
                    # TODO: Move this to the caller sometime
                    self.ut.log_event_receipt(event, 'dlgroup:addaddr')
                except (ExchangeException, ServerUnavailableException), e:
                    self.logger.warn('eid:%d: Can\'t add %s to %s: %s' %
                                     (event['event_id'], address, gname, e))
                    raise EventExecutionException
        else:
            # If we can't handle the object type, silently discard it
            raise EntityTypeError

    @EventDecorator.RegisterHandler(['email_address:rem_address'])
    def remove_address(self, event):
        """Event handler method used for removing e-mail addresses to
        accounts and distribution groups.

        :type event: Cerebrum.extlib.db_row.row
        :param event: The event returned from Change- or EventLog.

        :raises ExchangeException: If all accounts could not be updated."""
        params = self.ut.unpickle_event_params(event)
        domain = self.ut.get_email_domain_info(params['dom_id'])['name']
        address = '%s@%s' % (params['lp'], domain)

        try:
            et_eid, eid, eit, hq, sq = self.ut.get_email_target_info(
                target_id=event['subject_entity'])
        except Errors.NotFoundError:
            # If we wind up here, we have recieved an event that is triggered
            # by entity:del or something. Is this a bug, or a feature? We'll
            # just define this event as unrelated.
            raise UnrelatedEvent

        if eit == self.co.entity_account:
            if self.mb_spread not in self.ut.get_account_spreads(eid):
                # If we wind up here, the user is not supposed to be in
                # Exchange :S
                raise UnrelatedEvent
            uname = self.ut.get_account_name(eid)
            try:
                self.ec.remove_mailbox_addresses(uname,
                                                 [address])
                self.logger.info('eid:%d: Removed %s from %s' %
                                 (event['event_id'], address, uname))
                # Log a reciept that represents completion of the operation in
                # ChangeLog.
                # TODO: Move this to the caller sometime
                self.ut.log_event_receipt(event, 'exchange:acc_addr_rem')
            except (ExchangeException, ServerUnavailableException), e:
                self.logger.warn('eid:%d: Can\'t remove %s from %s: %s' %
                                 (event['event_id'], address, uname, e))
                raise EventExecutionException

        elif eit == self.co.entity_group:
            group_spreads = self.ut.get_group_spreads(eid)
            # TODO: Do we need this? Could this happen?
            if self.group_spread in group_spreads:
                gname, desc = self.ut.get_group_information(eid)
                try:
                    self.ec.remove_distgroup_addresses(gname, [address])
                    self.logger.info('eid:%d: Removed %s from %s' %
                                     (event['event_id'], address, gname))
                    # Log a reciept that represents completion of the operation
                    # in ChangeLog.
                    # TODO: Move this to the caller sometime
                    self.ut.log_event_receipt(event, 'dlgroup:remaddr')
                except (ExchangeException, ServerUnavailableException), e:
                    self.logger.warn('eid:%d: Can\'t remove %s from %s: %s' %
                                     (event['event_id'], address, gname, e))
                    raise EventExecutionException
        else:
            # If we can't handle the object type, silently discard it
            raise EntityTypeError

    @EventDecorator.RegisterHandler(['email_primary_address:add_primary',
                                     'email_primary_address:mod_primary',
                                     'email_primary_address:rem_primary'])
    def set_primary_address(self, event):
        """Event handler method used for setting the primary
        e-mail addresses of accounts and distribution groups.

        :type event: Cerebrum.extlib.db_row.row
        :param event: The event returned from Change- or EventLog.

        :raises ExchangeException: If all accounts could not be updated."""
        try:
            et_eid, eid, eit, hq, sq = self.ut.get_email_target_info(
                target_id=event['subject_entity'])
        except Errors.NotFoundError:
            # If we wind up here, we have recieved an event that is triggered
            # by entity:del or something. Is this a bug, or a feature? We'll
            # just define this event as unrelated.
            raise UnrelatedEvent

        if eit == self.co.entity_account:
            uname = self.ut.get_account_name(eid)
            if self.mb_spread not in self.ut.get_account_spreads(eid):
                # If we wind up here, the user is not supposed to be in
                # Exchange :S
                raise UnrelatedEvent
            addr = self.ut.get_account_primary_email(eid)
            try:
                self.ec.set_primary_mailbox_address(uname, addr)
                self.logger.info(
                    'eid:%d: Changing primary address of %s to %s' %
                    (event['event_id'], uname, addr))
                # Log a reciept that represents completion of the operation
                # in ChangeLog.
                # TODO: Move this to the caller sometime
                self.ut.log_event_receipt(event, 'exchange:acc_primaddr')

            except (ExchangeException, ServerUnavailableException), e:
                self.logger.warn(
                    'eid:%d: Can\'t change primary address of %s to %s: %s' %
                    (event['event_id'], uname, addr, e))
                raise EventExecutionException
        else:
            # If we can't handle the object type, silently discard it
            raise EntityTypeError

#####
# Group related commands
#####

    @EventDecorator.RegisterHandler(['spread:add'])
    def create_group(self, event):
        """Event handler for creating roups upon addition of
        spread.

        :type event: Cerebrum.extlib.db_row.row
        :param event: The event returned from Change- or EventLog."""
        gname = None
        # TODO: Handle exceptions!
        # TODO: Implicit checking of type. Should it be excplicit?
        added_spread_code = self.ut.unpickle_event_params(event)['spread']
        if added_spread_code == self.group_spread:
            gname, desc = self.ut.get_group_information(
                event['subject_entity'])
            try:
                data = self.ut.get_distgroup_attributes_and_targetdata(
                    event['subject_entity'])
            except Errors.NotFoundError:
                self.logger.warn(
                    'eid:%d: Can\'t find group %d' %
                    (event['event_id'], event['subject_entity']))
                raise EventExecutionException
            # TODO: Split up new_group and new_roomlist? create requeueing of
            # mailenabling?
            if data['roomlist'] == 'F':
                try:
                    self.ec.new_group(gname, self.config['group_ou'])
                    self.logger.info('eid:%d: Created Exchange group %s' %
                                     (event['event_id'], gname))
                    self.ut.log_event_receipt(event, 'dlgroup:create')
                except (ExchangeException, ServerUnavailableException), e:
                    self.logger.warn('eid:%d: Could not create group %s: %s' %
                                     (event['event_id'], gname, e))
                    raise EventExecutionException
            else:
                try:
                    self.ec.new_roomlist(gname, self.config['group_ou'])
                    self.logger.info('eid:%d: Created roomlist %s' %
                                     (event['event_id'], gname))
                    self.ut.log_event_receipt(event, 'dlgroup:roomcreate')
                except (ExchangeException, ServerUnavailableException), e:
                    self.logger.warn(
                        'eid:%d: Could not create roomlist %s: %s' %
                        (event['event_id'], gname, e))
                    raise EventExecutionException

            try:
                self.ec.set_distgroup_address_policy(gname)
                self.logger.info(
                    'eid:%d: Disabling Ex address policy for %s' %
                    (event['event_id'], gname))
            except (ExchangeException, ServerUnavailableException), e:
                self.logger.warn(
                    'eid:%d: Could not disable address policy for %s %s' %
                    (event['event_id'], gname, e))
                self.ut.log_event(event, 'exchange:set_ea_policy')

            # Only for pure distgroups :)
            if data['roomlist'] == 'F':
                # Set primary address
                try:
                    self.ec.set_distgroup_primary_address(gname,
                                                          data['primary'])
                    self.logger.info(
                        'eid:%d: Set primary %s for %s' %
                        (event['event_id'], data['primary'], gname))
                    self.ut.log_event_receipt(event, 'dlgroup:primary')
                except (ExchangeException, ServerUnavailableException), e:
                    self.logger.warn(
                        'eid:%d: Can\'t set primary %s for %s: %s' %
                        (event['event_id'], data['primary'], gname, e))
                    # TODO: This won't really work. Not implemented. Fix it
                    # somehow
                    # We create another event to set the primary address since
                    # setting it now failed
                    ev_mod = event.copy()
                    ev_mod['subject_entity'], tra, sh, hq, sq = \
                        self.ut.get_email_target_info(
                            target_entity=event['subject_entity'])
                    self.ut.log_event(
                        ev_mod, 'email_primary_address:add_primary')

                # Set mailaddrs
                try:
                    self.ec.add_distgroup_addresses(gname, data['aliases'])
                    self.logger.info('eid:%d: Set addresses for %s: %s' %
                                     (event['event_id'], gname,
                                      str(data['aliases'])))
                    # TODO: More resolution here? We want to mangle the event
                    # to show addresses?
                    self.ut.log_event_receipt(event, 'dlgroup:addaddr')

                except (ExchangeException, ServerUnavailableException), e:
                    self.logger.warn(
                        'eid:%d: Can\'t set addresses %s for %s: %s' %
                        (event['event_id'], str(data['aliases']), gname, e))
                    # TODO: Refactor this out
                    ev_mod = event.copy()
                    ev_mod['subject_entity'], tra, sh, hq, sq = \
                        self.ut.get_email_target_info(
                            target_entity=event['subject_entity'])
                    for x in data['aliases']:
                        x = x.split('@')
                        info = self.ut.get_email_domain_info(
                            email_domain_name=x[1])
                        # TODO: UTF-8 error?
                        ev_mod['change_params'] = pickle.dumps(
                            {'dom_id': info['id'], 'lp': x[0]})
                        self.ut.log_event(ev_mod, 'email_address:add_address')

                # Set hidden
                try:
                    hide = True if data['hidden'] == 'T' else False
                    self.ec.set_distgroup_visibility(gname, hide)
                    self.logger.info(
                        'eid:%d: Set %s visible: %s' %
                        (event['event_id'], gname, data['hidden']))
                    self.ut.log_event_receipt(event, 'dlgroup:modhidden')
                except (ExchangeException, ServerUnavailableException), e:
                    self.logger.warn(
                        'eid:%d: Can\'t set visibility for %s: %s' %
                        (event['event_id'], gname, e))
                    ev_mod = event.copy()
                    ev_mod['change_params'] = pickle.dumps(
                        {'hidden': data['hidden']})
                    self.ut.log_event(ev_mod, 'dlgroup:modhidden')

            # Set manager
            mngdby_address = cereconf.DISTGROUP_DEFAULT_ADMIN
            try:
                self.ec.set_distgroup_manager(gname, mngdby_address)
                self.logger.info(
                    'eid:%d: Set manager of %s to %s' %
                    (event['event_id'], gname, mngdby_address))
                self.ut.log_event_receipt(event, 'dlgroup:modmanby')
            except (ExchangeException, ServerUnavailableException), e:
                self.logger.warn(
                    'eid:%d: Can\'t set manager of %s to %s: %s' %
                    (event['event_id'], gname, mngdby_address, e))
                ev_mod = event.copy()
                ev_mod['change_params'] = pickle.dumps(
                    {'manby': mngdby_address})
                self.ut.log_event(ev_mod, 'dlgroup:modmanby')
            tmp_fail = False
            # Set displayname
            try:
                self.ec.set_group_display_name(gname, data['displayname'])
                self.logger.info(
                    'eid:%d: Set displayname to %s for %s' %
                    (event['event_id'], data['displayname'], gname))
            except (ExchangeException, ServerUnavailableException), e:
                self.logger.warn(
                    'eid:%d: Can\'t set displayname to %s for %s: %s'
                    % (event['event_id'], data['displayname'], gname, e))
                tmp_fail = True

            # Set description
            # TODO: This if ain't needed for distgroups, yes?
            # TODO: Should we rarther pull this from get_group_information?
            if data['description']:
                try:
                    self.ec.set_distgroup_description(
                        gname, data['description'])
                    self.logger.info(
                        'eid:%d: Set description to %s for %s' %
                        (event['event_id'], data['description'], gname))
                except (ExchangeException, ServerUnavailableException), e:
                    self.logger.warn(
                        'eid:%d: Can\'t set description to %s for %s: %s' %
                        (event['event_id'], data['description'], gname, e))
                    tmp_fail = True

            if tmp_fail:
                # Log a "new" event for updating display name and description
                # We don't mangle the event here, since the only thing we care
                # about when updating the name or description is the
                # subject_entity.
                self.ut.log_event(event, 'entity_name:mod')

        else:
            # TODO: Fix up this comment, it is not the entire truth.
            # If we can't handle the object type, silently discard it
            self.logger.debug2('eid:%d: UnrelatedEvent' % event['event_id'])
            raise UnrelatedEvent

# TODO: SPlit this out in its own function depending on spread:add
        # Put group members inside the group
        # As of now we do this by generating an event for each member that
        # should be added. This is the quick and relatively painless solution,
        # altough performance will suffer greatly.
        members = [uname for uname in self.ut.get_group_members(
            event['subject_entity'],
            spread=self.mb_spread,
            filter_spread=self.ad_spread)]
        for memb in members:
            ev_mod = event.copy()
            ev_mod['dest_entity'] = ev_mod['subject_entity']
            ev_mod['subject_entity'] = memb['account_id']
            self.logger.debug1(
                'eid:%d: Creating event: Adding %s to %s' %
                (event['event_id'], memb['name'], gname))
            self.ut.log_event(ev_mod, 'e_group:add')

    @EventDecorator.RegisterHandler(['dlgroup:remove'])
    def remove_group(self, event):
        """Removal of group when spread is removed.

        :type event: Cerebrum.extlib.db_row.row
        :param event: The event returned from Change- or EventLog."""
        data = self.ut.unpickle_event_params(event)
        if data['roomlist'] == 'F':
            try:
                self.ec.remove_group(data['name'])
                self.logger.info('eid:%d: Removed group %s' %
                                 (event['event_id'], data['name']))
                self.ut.log_event_receipt(event, 'dlgroup:remove')

            except (ExchangeException, ServerUnavailableException), e:
                self.logger.warn('eid:%d: Couldn\'t remove group %s' %
                                 (event['event_id'], data['name']))
                raise EventExecutionException
        else:
            try:
                self.ec.remove_roomlist(data['name'])
                self.logger.info('eid:%d: Removed roomlist %s' %
                                 (event['event_id'], data['name']))
                self.ut.log_event_receipt(event, 'dlgroup:remove')

            except (ExchangeException, ServerUnavailableException), e:
                self.logger.warn('eid:%d: Couldn\'t remove roomlist %s: %s' %
                                 (event['event_id'], data['name'], e))
                raise EventExecutionException

    @EventDecorator.RegisterHandler(['e_group:add'])
    def add_group_member(self, event):
        """Addition of member to group.

        :type event: Cerebrum.extlib.db_row.row
        :param event: The event returned from Change- or EventLog.

        :raise UnrelatedEvent: If this event is unrelated to this handler.
        :raise EventExecutionException: If the event fails to execute."""
        # Look up group information (eid and spreads)
        # Look up member for removal
        # Remove from group type according to spread

        # Collect information about the group, and see if we should handle it
        group_spreads = self.ut.get_group_spreads(event['dest_entity'])

        if self.group_spread not in group_spreads:
            self.logger.debug2('eid:%d: Unsupported group type for gid=%s!' %
                               (event['event_id'], event['dest_entity']))
            # Silently discard it
            raise UnrelatedEvent

        gname, description = self.ut.get_group_information(
            event['dest_entity'])

        add_to_groups = [gname]

        # Check to see if we should do something with this member, and fetch
        # some information about the member
        et = self.ut.get_entity_type(event['subject_entity'])
        if et == self.co.entity_account:
            uname = self.ut.get_account_name(event['subject_entity'])
            aid = event['subject_entity']
        elif et == self.co.entity_person:
            aid = self.ut.get_primary_account(event['subject_entity'])
            uname = self.ut.get_account_name(aid)

            # Look for derived groups (like meta-ansatt-something), that we
            # should add the user to
            for gnt in self.group_name_translation:
                if gname.startswith(gnt):
                    add_to_groups.extend(self.ut.get_parent_groups(
                                         event['dest_entity'],
                                         self.group_spread,
                                         self.group_name_translation[gnt]))
        else:
            # Can't handle this memeber type
            raise EntityTypeError

        # If the users does not have an AD- or an Exchange-spread, it should
        # never end up in a group! So we fetch the spreads and check..
        member_spreads = self.ut.get_account_spreads(aid)

        if self.mb_spread not in member_spreads:
            raise UnrelatedEvent
        if self.ad_spread not in member_spreads:
            raise EventExecutionException('No AD-spread on user :S')

        for group in add_to_groups:
            try:
                self.ec.add_distgroup_member(group, uname)
                self.logger.info('eid:%d: Added %s to %s' %
                                 (event['event_id'], uname, group))
                # Copy & mangle the event, so we can log it correctly
                # TBD: Should we also log the parent group id in change params?
                mod_ev = event.copy()
                # TODO: Cache group ids instead of looking it up like this.
                mod_ev['dest_entity'] = self.ut.get_group_id(group)
                self.ut.log_event_receipt(mod_ev, 'dlgroup:add')
            except (ExchangeException, ServerUnavailableException), e:
                self.logger.warn('eid:%d: Can\'t add %s to %s: %s' %
                                 (event['event_id'], uname, gname, e))
                # Create a faux-event if the event fails, and the entity added
                # is a person. Do not create a faux-event if the entity added
                # is a user.
                if et == self.co.entity_person:
                    ev_mod = event.copy()
                    ev_mod['dest_entity'] = self.ut.get_group_id(group)
                    self.logger.debug1(
                        'eid:%d: Creating event: Adding %s to %s' %
                        (event['event_id'], uname, gname))
                    self.ut.log_event(ev_mod, 'e_group:add')
                else:
                    raise EventExecutionException
            except AlreadyPerformedException:
                # If we wind up here, the user was allready added. We might, in
                # some circumstances, want to discard the event completely, but
                # for now, we just pass along.
                self.logger.debug1(
                    'eid:%d: Discarding e_group:add (%s into %s)' %
                    (event['event_id'], uname, gname))
                # Copy & mangle the event, so we can log it correctly
                # TBD: Should we also log the parent group id in change params?
                mod_ev = event.copy()
                # TODO: Cache group ids instead of looking it up like this.
                mod_ev['dest_entity'] = self.ut.get_group_id(group)
                mod_ev['change_params'] = pickle.dumps({'AlreadyPerformed':
                                                        True})
                self.ut.log_event_receipt(mod_ev, 'dlgroup:add')

    @EventDecorator.RegisterHandler(['e_group:rem'])
    def remove_group_member(self, event):
        """Removal of member from group.

        :type event: Cerebrum.extlib.db_row.row
        :param event: The event returned from Change- or EventLog.

        :raise UnrelatedEvent: Raised if the event is not to be handled."""
        # Look up group information (eid and spreads)
        # Look up member for removal
        # Remove from group type according to spread
        group_spreads = self.ut.get_group_spreads(event['dest_entity'])

        if self.group_spread not in group_spreads:
            self.logger.debug2('eid:%d: Unsupported group type for gid=%s!' %
                               (event['event_id'], event['subject_entity']))
            # Silently discard it
            raise UnrelatedEvent

        gname, description = self.ut.get_group_information(
            event['dest_entity'])

        rem_from_groups = [gname]

        # Check to see if we should do something with this member,
        # and fetch some info.
        et = self.ut.get_entity_type(event['subject_entity'])
        if et == self.co.entity_account:
            uname = self.ut.get_account_name(event['subject_entity'])
            aid = event['subject_entity']
        elif et == self.co.entity_person:
            aid = self.ut.get_primary_account(event['subject_entity'])
            uname = self.ut.get_account_name(aid)

            # Look for derived groups (like meta-ansatt-something), that we
            # should remove the user to
            for gnt in self.group_name_translation:
                if gname.startswith(gnt):
                    rem_from_groups.extend(self.ut.get_parent_groups(
                                           event['dest_entity'],
                                           self.group_spread,
                                           self.group_name_translation[gnt]))
        else:
            # Can't handle this memeber type
            raise EntityTypeError

        # If the users does not have an AD-spread, we can't remove em. Or can
        # we?
        # TODO: Figure this out. This is relevant for removal of persons from
        # exchange.
        member_spreads = self.ut.get_account_spreads(aid)

        # Can't remove that user from the group ;)
        if self.mb_spread not in member_spreads:
            raise UnrelatedEvent
        if self.ad_spread not in member_spreads:
            # TODO: Return? That is NOT sane.
            return

        for group in rem_from_groups:
            try:
                # TODO: We should check if the user to remove exists first.. If
                # it does not, it has allready been removed.. This would
                # probably be smart to do, in order to reduce noise in da logs.
                self.ec.remove_distgroup_member(group, uname)
                self.logger.info('eid:%d: Removed %s from %s' %
                                 (event['event_id'], uname, group))
                # Copy & mangle the event, so we can log it reciept correctly
                # TBD: Should we also log the parent group id in change params?
                mod_ev = event.copy()
                # TODO: Cache group ids instead of looking it up like this.
                mod_ev['dest_entity'] = self.ut.get_group_id(group)
                self.ut.log_event_receipt(mod_ev, 'dlgroup:rem')
            except (ExchangeException, ServerUnavailableException), e:
                self.logger.warn('eid:%d: Can\'t remove %s from %s: %s' %
                                 (event['event_id'], uname, gname, e))
#                # Log an event so this will happen sometime (hopefully)
#                ev_mod = event.copy()
#                ev_mod['dest_entity'] = self.ut.get_group_id(group)
#                self.logger.debug1(
#                    'eid:%d: Creating event: Removing %s from %s' %
#                    (event['event_id'], uname, group))
#                self.ut.log_event(ev_mod, 'e_group:rem')

    @EventDecorator.RegisterHandler(['dlgroup:modhidden'])
    def set_group_visibility(self, event):
        """Set the visibility of a group.

        :type event: Cerebrum.extlib.db_row.row
        :param event: The event returned from Change- or EventLog."""
        group_spreads = self.ut.get_group_spreads(event['subject_entity'])
        gname, description = self.ut.get_group_information(
            event['subject_entity'])
        params = self.ut.unpickle_event_params(event)

        if self.group_spread in group_spreads:

            # Reverse logic, gotta love it!!!11
            show = True if params['hidden'] == 'T' else False
            try:
                self.ec.set_distgroup_visibility(gname, show)
                self.logger.info(
                    'eid:%d: Group visibility set to %s for %s' %
                    (event['event_id'], show, gname))

                # Log a reciept that represents completion of the operation
                # in ChangeLog.
                # TODO: Move this to the caller sometime
                self.ut.log_event_receipt(event, 'dlgroup:modhidden')
            except (ExchangeException, ServerUnavailableException), e:
                self.logger.warn(
                    'eid:%d: Can\'t set hidden to %s for %s: %s' %
                    (event['event_id'], show, gname, e))
                raise EventExecutionException
        else:
            # TODO: Will we ever arrive here? Log this?
            raise UnrelatedEvent

    @EventDecorator.RegisterHandler(['dlgroup:modmanby'])
    def set_distgroup_manager(self, event):
        """Set a distribution groups manager.

        :type event: Cerebrum.extlib.db_row.row
        :param event: The event returned from Change- or EventLog."""
        # TODO: More type chacking?
        gname, description = self.ut.get_group_information(
            event['subject_entity'])
        params = self.ut.unpickle_event_params(event)
        mngdby_address = cereconf.DISTGROUP_DEFAULT_ADMIN
        try:
            self.ec.set_distgroup_manager(gname, mngdby_address)
            # TODO: Better logging
            self.logger.info('eid:%d: Setting manager %s for %s' %
                             (event['event_id'], mngdby_address, gname))

            # Log a reciept that represents completion of the operation
            # in ChangeLog.
            # TODO: Move this to the caller sometime
            self.ut.log_event_receipt(event, 'dlgroup:modmanby')
        except (ExchangeException, ServerUnavailableException), e:
            self.logger.warn('eid:%d: Failed to set manager %s for %s: %s' %
                             (event['event_id'], mngdby_address, gname, e))
            raise EventExecutionException

    @EventDecorator.RegisterHandler(['dlgroup:moddepres', 'dlgroup:modjoinre'])
    def set_distgroup_restriction(self, event):
        """Set depart and join restrictions on a distribution group.

        :type event: Cerebrum.extlib.db_row.row
        :param event: The event returned from Change- or EventLog."""
        # TODO: More type checking?
        gname, description = self.ut.get_group_information(
            event['subject_entity'])
        params = self.ut.unpickle_event_params(event)
        part = params.get('deprestr', None)
        join = params.get('joinrestr', None)
        try:
            self.ec.set_distgroup_member_restrictions(gname, join, part)
            # TODO: Clarify this

            # Log a reciept that represents completion of the operation
            # in ChangeLog.
            # TODO: Move this to the caller sometime
            if join:
                self.ut.log_event_receipt(event, 'dlgroup:modjoinre')
                self.logger.info('eid:%d: Set join restriction to %s for %s' %
                                 (event['event_id'], join, gname))
            if part:
                self.ut.log_event_receipt(event, 'dlgroup:moddepres')
                self.logger.info('eid:%d: Set part restriction to %s for %s' %
                                 (event['event_id'], part, gname))
        except (ExchangeException, ServerUnavailableException), e:
            self.logger.warn(
                'eid:%d: Can\'t set join/part restriction on %s: %s' %
                (event['event_id'], gname, e))
            raise EventExecutionException

    # TODO: Is add and del relevant?
    # TODO: This works for description?
    @EventDecorator.RegisterHandler(['entity_name:add', 'entity_name:mod',
                                     'entity_name:del'])
    def set_group_description_and_name(self, event):
        """Update displayname / description on a group.

        :type event: Cerebrum.extlib.db_row.row
        :param event: The event returned from Change- or EventLog."""
        try:
            et = self.ut.get_entity_type(event['subject_entity'])
            if not et == self.co.entity_group:
                raise Errors.NotFoundError
            # If we can't find a person with this entity id, we silently
            # discard the event by doing nothing
        except Errors.NotFoundError:
            raise EntityTypeError

        group_spreads = self.ut.get_group_spreads(event['subject_entity'])
        # If it is a security group, load info and set display name
        if self.group_spread in group_spreads:
            attrs = self.ut.get_distgroup_attributes_and_targetdata(
                event['subject_entity'])

            # Set the display name
            try:
                self.ec.set_group_display_name(attrs['name'],
                                               attrs['displayname'])
                self.logger.info(
                    'eid:%d: Set displayname on %s to %s' %
                    (event['event_id'], attrs['name'], attrs['name']))
            except (ExchangeException, ServerUnavailableException), e:
                self.logger.warn(
                    'eid:%d: can\'t set displayname on %s to %s: %s' %
                    (event['event_id'], attrs['name'], attrs['name'], e))

            # Set the description
            try:
                self.ec.set_distgroup_description(attrs['name'],
                                                  attrs['description'])
                self.logger.info(
                    'eid:%d: Set description on %s to %s' %
                    (event['event_id'], attrs['name'], attrs['description']))
            except (ExchangeException, ServerUnavailableException), e:
                self.logger.warn(
                    'eid:%d: Can\'t set description on %s to %s: %s' %
                    (event['event_id'], attrs['name'],
                        attrs['description'], e))
                raise EventExecutionException

            else:
                # TODO: Correct exception? Think about it
                raise UnrelatedEvent
