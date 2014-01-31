#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2014 University of Oslo, Norway
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

import random
import processing

from Queue import Empty
import pickle
import traceback

from Cerebrum.modules.exchange.v2013.ExchangeClient import ExchangeClient
from Cerebrum.modules.exchange.Exceptions import ExchangeException
#from Cerebrum.modules.exchange.Exceptions import ObjectNotFoundException
#from Cerebrum.modules.exchange.Exceptions import ADError
from Cerebrum.modules.exchange.CerebrumUtils import CerebrumUtils
from Cerebrum.modules.event.EventExceptions import EventExecutionException
from Cerebrum.modules.event.EventExceptions import EventHandlerNotImplemented
from Cerebrum.modules.event.EventExceptions import EntityTypeError
from Cerebrum.modules.event.EventExceptions import UnrelatedEvent
from Cerebrum.modules.event.EventDecorator import EventDecorator
from Cerebrum.modules.event.HackedLogger import Logger

from Cerebrum.Utils import Factory
from Cerebrum import Errors


# The following code can be used for quick testing of the Cerebrum side
# of stuff. We fake the client, and always return True :D This way, we
# can quickly run through a fuckton of events.
class PI(object):
    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, a):
        return lambda *args, **kwargs: True
#ExchangeClient = PI

class ExchangeEventHandler(processing.Process):
    # Event to method lookup table. Populated by decorators.
    _lut_type2meth = {}
    def __init__(self, config, event_queue, logger_queue, run_state):
        """ExchangeEventHandler initialization routine

        @type config: dict
        @param config: Dict containing the config for the ExchangeClient
            and handler

        @type event_queue: processing.Queue
        @param event_queue: The queue that events get queued on
        
        @type logger: processing.Queue
        @param logger: Put tuples like ('warn', 'my message') onto this
            queue in order to have them logged

        @type run_state: processing.Value(ctypes.c_int)
        @param run_state: A shared object used to determine if we should
            stop execution or not
        """
        self.event_queue = event_queue
        self.run_state = run_state
        self.config = config
        # TODO: This is a hack. Fix it
        self.logger_queue = logger_queue
        self.logger = Logger(self.logger_queue)
        
        super(ExchangeEventHandler, self).__init__()

    def _post_fork_init(self):
        """Post-fork init method.

        We need to initialize the database-connection after we fork,
        or else we will get random errors since all the threads share
        the same sockets.. This is somewhat documented here:
        http://www.postgresql.org/docs/current/static/libpq-connect.html \
                #LIBPQ-CONNECT

        We also initialize the ExchangeClient here.. We can start faster
        when we do it in paralell.
        """
        gen_key = lambda: 'CB%s' \
                % hex(random.randint(0xF00000,0xFFFFFF))[2:].upper()
        self.ec = ExchangeClient(logger=self.logger,
                     host=self.config['server'],
                     port=self.config['port'],
                     auth_user=self.config['auth_user'],
                     domain_admin=self.config['domain_admin'],
                     ex_domain_admin=self.config['ex_domain_admin'],
                     management_server=self.config['management_server'],
                     encrypted=self.config['encrypted'],
                     session_key=gen_key())

        # Initialize the Database and Constants object
        self.db = Factory.get('Database')(client_encoding='UTF-8')
        self.co = Factory.get('Constants')(self.db)
        
        # Spreads to use!
        self.mb_spread = self.co.Spread(self.config['mailbox_spread'])
        self.dg_spread = self.co.Spread(self.config['distgroup_spread'])
        self.sg_spread = self.co.Spread(self.config['secgroup_spread'])
        self.ad_spread = self.co.Spread(self.config['ad_spread'])

        # Throw away our implicit transaction after fetching spreads
        self.db.rollback()

        # Initialise the Utils. This contains functions to pull data from
        # Cerebrum
        self.ut = CerebrumUtils()

    def run(self):
        """Main event-processing loop. Spawned by processing.Process.__init__
        """
        # When we execute code here, we have forked. We can now initialize
        # the database (and more)
        self._post_fork_init()

        # It is a bit ugly to directly access a processing.Value object
        # like this, but it is simple and it works. Doing something like
        # this with more "pythonic" types adds a lot of complexity.
        self.logger.debug2('Listening for events')
        while self.run_state.value:
            # Collect a new event.
            try:
                ev = self.event_queue.get(block=True, timeout=5)
            except Empty:
                # We continue here, since the queue will be empty
                # at times.
                continue
            self.logger.debug3('Got a new event: %s' % str(ev))
            
            # Try to lock the event
            try:
                ev_id = self.db.lock_event(ev['payload'])
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

            # Fetch the event after it has been locked 
            ev_log = self.db.get_event(ev_id)
            
            # We try to handle the event
            try:
                self.handle_event(ev_log)
                # When the command(s) have run sucessfully, we remove the
                # the triggering event.
                self.db.remove_event(ev_log['event_id'])
                # TODO: Store the receipt in ChangeLog! We need to handle
                # EntityTypeError and UnrelatedEvent in a appropriate manner
                # for this to work.
                self.db.commit()
            # If the event fails, we append the event to the queue
            # If an event fails, we just release it, and let the
            # DelayedNotificationCollector enqueue it when appropriate
            except EventExecutionException, e:
                self.logger.debug('Failed to process event %d: %s' % \
                                        (ev_log['event_id'], str(e)))
                self.db.release_event(ev_log['event_id'])
                self.db.commit()
            except EventHandlerNotImplemented:
                # TODO: Should we log this?
                self.logger.debug3('Event Handler Not Implemented!')
                # We remove the event for now.. Or else it will just
                # sit around for a loooong time...
                self.db.remove_event(ev_log['event_id'])
                self.db.commit()
#            except (EntityTypeError, UnrelatedEvent):
#                # When this gets raised, the owner type of the object
#                # is probably wrong. We silently discard the event
#                self.db.remove_event(ev_log['event_id'])
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
                # IS therefore REQUIRED!!!!!!1
                #
                # Get the traceback, put some tabs in front, and log it.
                tb = traceback.format_exc()
                tb = '\t' + tb.replace('\n', '\t\n')
                self.logger.error(
                        'Oops! Didn\'t see that one coming! :)\n%s\n%s' % \
                                (str(ev_log), tb))
                # We unlock the event, so it can be retried
                self.db.release_event(ev_log['event_id'])
                self.db.commit()

        # When the run-state has been set to 0, we kill the pssession
        self.ec.kill_session()
        self.ec.close()
        self.logger.debug('ExchangeEventHandler stopped')

    def handle_event(self, event):
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
        """Event handler method responsible for creating new mailboxes,
        when an account gets an appropriate spread.

        @type event: Cerebrum.extlib.db_row.row
        @param event: The event returned from Change- or EventLog
        """
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
                first_name, last_name, full_name = \
                    self.ut.get_person_names(person_id=eid)

                hide_from_address_book = \
                        self.ut.is_electronic_reserved(person_id=eid) or \
                        not event['subject_entity'] == \
                            self.ut.get_primary_account(person_id=eid)

            # Then for accounts owned by groups
            elif et == self.co.entity_group:
                first_name = last_name = ''
                # 'full_name' is really the description :) Ugly, but less code.
                gname, full_name = self.ut.get_group_information(eid)

                # TODO: Is this ok?
                hide_from_address_book = False
            else:
                # An exchange-spread has been given to an account not owned
                # by a person or a group
                self.logger.warn(
                'Account %s is not owned by a person or group. Skipping..' \
                                % uname)
                # Raise exception, this should result in silent discard
                raise EntityTypeError

            # Create the mailbox
            try:
                self.ec.new_mailbox(uname, full_name,
                                    first_name, last_name,
                                    ou=self.config['mailbox_path'])
                self.logger.info('Created new mailbox for %s' \
                        % uname)
                # TODO: Should we log a receipt for hiding the mbox in the
                # address book? We don't really need to, since everyone is
                # hidden by default.
                self.ut.log_event_receipt(event, 'exchange:acc_mbox_create')
            except ExchangeException, e:
                self.logger.warn('Failed creating mailbox for %s: %s' \
                        % (uname, e))
                raise EventExecutionException

            # Disable the email address policy
            try:
                self.ec.set_mailbox_address_policy(uname,
                                                   enabled=False)
            except ExchangeException, e:
                self.logger.warn('Failed disabling address policy for %s' \
                        % uname)
                self.ut.log_event(event, 'exchange:set_ea_policy')
                # TODO: Should we do this here? Should we rather do it in the address
                # policy handler?
                ev_mod = event.copy()
                ev_mod['subject_entity'], tra, sh, hq, sq = \
                        self.ut.get_email_target_info(
                                target_entity=event['subject_entity'])
                self.ut.log_event(ev_mod, 'email_primary_address:add_primary')
            
            if not hide_from_address_book:
                try:
                    self.ec.set_mailbox_visibility(
                            uname, visible=True)
                    self.logger.info('Publishing %s in address book...' \
                            % uname)
                    # TODO: Mangle the event som it represents this correctly??
                    self.ut.log_event_receipt(event, 'exchange:per_e_reserv')
                except ExchangeException, e:
                    self.logger.warn(
                            'Could not publish %s in address book' \
                            % uname)
                    self.ut.log_event(event, 'trait:add')

            # Collect'n set valid addresses for the mailbox
            addrs = self.ut.get_account_mailaddrs(event['subject_entity'])
            try:
                self.ec.add_mailbox_addresses(uname, addrs)
                self.logger.info('Added addresses for %s' % \
                                    uname)
                # TODO: Higher resolution? Should we do this for all addresses,
                # and mangle the event to represent this?
                self.ut.log_event_receipt(event, 'exchange:acc_addr_add')
            except ExchangeException, e:
                self.logger.warn('Could not add e-mail addresses for %s' \
                        % uname)
                # Creating new events in case this fails
                mod_ev = event.copy()
                for x in addrs:
                    x = x.split('@')
                    info = self.ut.get_email_domain_info(email_domain_name=x[1])
                    mod_ev['change_params'] = pickle.dumps(
                                            {'dom_id': info['id'], 'lp': x[0]})
                    mod_ev['subject_entity'], tra, sh, hq, sq = \
                            self.ut.get_email_target_info(
                                    target_entity=event['subject_entity'])
                    self.ut.log_event(mod_ev, 'email_address:add_address')

            # Set the primary mailaddress
            pri_addr = self.ut.get_account_primary_email(
                                                event['subject_entity'])
            try:
                self.ec.set_primary_mailbox_address(uname,
                                                    pri_addr)
                self.logger.info('Defined primary address for %s' % \
                                    uname)
                self.ut.log_event_receipt(event, 'exchange:acc_primaddr')

            except ExchangeException, e:
                self.logger.warn('Could not set primary address on %s'\
                        % uname)
                # Creating a new event in case this fails
                ev_mod = event.copy()
                ev_mod['subject_entity'], tra, sh, hq, sq = \
                        self.ut.get_email_target_info(
                                target_entity=event['subject_entity'])
                self.ut.log_event(ev_mod, 'email_primary_address:add_primary')

            # Set the initial quota
            aid = self.ut.get_account_id(uname)

            et_eid, tid, tt, hq, sq = self.ut.get_email_target_info(
                                                        target_entity=aid) 
            try:
                soft = (hq * sq) / 100
                self.ec.set_mailbox_quota(uname, soft, hq)
                self.logger.info('Set quota (%s, %s) on %s' % \
                                 (soft, hq, uname))
            except ExchangeException, e:
                self.logger.warn('Could not set quota on %s: %s' % (uname, e))
                # Log an event for setting the quota if it fails for some reason
                mod_ev = {'dest_entity': None, 'subject_entity': et_eid}
                mod_ev['change_params'] = pickle.dumps(
                                                    {'soft': sq,
                                                     'hard': hq})
                self.ut.log_event(mod_ev, 'email_quota:add_quota')

        # If we wind up here, the spread type is notrelated to our target system
        else:
            raise UnrelatedEvent

    @EventDecorator.RegisterHandler(['spread:delete'])
    def remove_mailbox(self, event):
        """Event handler for removal of mailbox when an account looses its
        spread
        
        @type event: Cerebrum.extlib.db_row.row
        @param event: The event returned from Change- or EventLog
        """
        removed_spread_code = self.ut.unpickle_event_params(event)['spread']
        if removed_spread_code == self.mb_spread:
            # TODO: This is highly temporary! Remove the following line when
            #       we have solved archiving of mailboxes ;)
            raise EventExecutionException
            uname = self.ut.get_account_name(event['subject_entity'])
            try:
                self.ec.remove_mailbox(uname)
                self.logger.debug2('Removed mailbox %s' % uname)
                # Log a reciept that represents completion of the operation in
                # ChangeLog.
                # TODO: Move this to the caller sometime
                self.ut.log_event_receipt(event, 'exchange:acc_mbox_delete')
            except ExchangeException, e:
                self.logger.warn('Couldn\'t remove mailbox for %s %s' % \
                        (uname, e))
                raise EventExecutionException

    @EventDecorator.RegisterHandler(['person:name_add', 'person:name_del',
                                     'person:name_mod'])
    def set_names(self, event):
        """Event handler method used for updating a persons accounts with
        the persons new name.

        @type event: Cerebrum.extlib.db_row.row
        @param event: The event returned from Change- or EventLog
        
        @raises ExchangeException: If all accounts could not be updated.
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
                    self.logger.info('Updated name for %s' % uname)
                except ExchangeException, e:
                    self.logger.warn('Failed updating name for %s: %s' % \
                            (uname, e))
                    raise EventExecutionException
            else:
                # If we wind up here, the user is not supposed to be in
                # Exchange :S
                raise UnrelatedEvent

    @EventDecorator.RegisterHandler(['trait:add', 'trait:mod', 'trait:del'])
    def set_address_book_visibility(self, event):
        """Set the visibility of a persons accounts in the address book.

        @type event: Cerebrum.extlib.db_row.row
        @param event: The event returned from Change- or EventLog
        
        @raises ExchangeException: If all accounts could not be updated.
        """
        try:
            et = self.ut.get_entity_type(event['subject_entity'])
            if not et == self.co.entity_person:
                raise Errors.NotFoundError
            # If we can't find a person with this entity id, we silently
            # discard the event by doing nothing
        except Errors.NotFoundError:
            raise EntityTypeError

        hidden_from_address_book = self.ut.is_electronic_reserved(
                                                person_id=event['subject_entity'])
        # We set visibility on all accounts the person owns, that has an
        # Exchange-spread
        for aid, uname in self.ut.get_person_accounts(event['subject_entity'],
                                             self.mb_spread):
            if not self.mb_spread in self.ut.get_account_spreads(aid):
                # If we wind up here, the user is not supposed to be in Exchange :S
                raise UnrelatedEvent
            if hidden_from_address_book:
                try:
                    self.ec.set_mailbox_visibility(uname, visible=False)
                    self.logger.debug2('Hiding id:%d in address book..' \
                                        % event['subject_entity'])
                except ExchangeException, e:
                    self.logger.warn('Can\'t hide %d in address book: %s' \
                                     % (event['subject_entity'], e))
                    raise EventExecutionException
            else:
                try:
                    self.ec.set_mailbox_visibility(uname, visible=True)
                    self.logger.debug2('Publishing id:%d in address book..' \
                                        % event['subject_entity'])
                except ExchangeException, e:
                    self.logger.warn('Can\'t publish %d in address book: %s' \
                                     % (event['subject_entity'], e))
                    raise EventExecutionException

        # Log a reciept that represents completion of the operation in
        # ChangeLog.
        # TODO: Move this to the caller sometime
        self.ut.log_event_receipt(event, 'exchange:per_e_reserv')

    @EventDecorator.RegisterHandler(['email_quota:add_quota',
                                     'email_quota:mod_quota',
                                     'email_quota:rem_quota'])
    def set_mailbox_quota(self, event):
        # TODO: Should we error check the reutrn from this method? Typewise that is
        try:
            et_eid, tid, tet, hq, sq = self.ut.get_email_target_info(
                                            target_id=event['subject_entity'])
        except Errors.NotFoundError:
            # If we wind up here, we have recieved an event that is triggered
            # by entity:del or something. Is this a bug, or a feature? We'll
            # just define this event as unrelated.
            raise UnrelatedEvent

        params = self.ut.unpickle_event_params(event)
        name = self.ut.get_account_name(tid)
        if not self.mb_spread in self.ut.get_account_spreads(tid):
            # If we wind up here, the user is not supposed to be in Exchange :S
            raise UnrelatedEvent
        try:
            hard = params['hard']
            soft = (params['hard'] * params['soft']) / 100

            self.ec.set_mailbox_quota(name, soft, hard)
            self.logger.info('Set quota (%d hard, %d soft) on mailbox for %s' \
                    % (hard, soft, name))
        except ExchangeException, e:
            self.logger.warn('Can\'t set quota (%d hard, %d soft) for %s: %s)' \
                    % (hard, soft, name, e))
            raise EventExecutionException

# TODO: Are these so "generic"?
####
# Generic functions
####
    @EventDecorator.RegisterHandler(['email_address:add_address'])
    def add_address(self, event):
        """Event handler method used for adding e-mail addresses to
        accounts and distribution groups.

        @type event: Cerebrum.extlib.db_row.row
        @param event: The event returned from Change- or EventLog
        
        @raises ExchangeException: If all accounts could not be updated.
        """
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
            if not self.mb_spread in self.ut.get_account_spreads(eid):
                # If we wind up here, the user is not supposed to be in Exchange :S
                raise UnrelatedEvent
            uname = self.ut.get_account_name(eid)
            try:
                self.ec.add_mailbox_addresses(uname, [address])
                self.logger.info('Added %s to %s' % 
                        (address, uname))

                # Log a reciept that represents completion of the operation in
                # ChangeLog.
                # TODO: Move this to the caller sometime
                self.ut.log_event_receipt(event, 'exchange:acc_addr_add')
            except ExchangeException, e:
                self.logger.warn('Can\'t add %s to %s: %s' % 
                                 (address, uname, e))
                raise EventExecutionException

        elif eit == self.co.entity_group:
            group_spreads = self.ut.get_group_spreads(eid)
            # TODO: Do we need this? Could this happen?
            if self.dg_spread in group_spreads:
                gname, desc = self.ut.get_group_information(eid)
                gname = self.config['distgroup_prefix'] + gname
                try:
                    self.ec.add_distgroup_addresses(gname, [address])
                    self.logger.info('Added %s to %s' % 
                            (address, gname))
                    # Log a reciept that represents completion of the operation
                    # in ChangeLog.
                    # TODO: Move this to the caller sometime
                    self.ut.log_event_receipt(event, 'dlgroup:addaddr')
                except ExchangeException, e:
                    self.logger.warn('Can\'t add %s to %s: %s' % 
                                     (address, gname, e))
                    raise EventExecutionException
        else:
            # If we can't handle the object type, silently discard it
            raise EntityTypeError

    @EventDecorator.RegisterHandler(['email_address:rem_address'])
    def remove_address(self, event):
        """Event handler method used for removing e-mail addresses to
        accounts and distribution groups.

        @type event: Cerebrum.extlib.db_row.row
        @param event: The event returned from Change- or EventLog
        
        @raises ExchangeException: If all accounts could not be updated.
        """
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
            if not self.mb_spread in self.ut.get_account_spreads(eid):
                # If we wind up here, the user is not supposed to be in Exchange :S
                raise UnrelatedEvent
            uname = self.ut.get_account_name(eid)
            try:
                self.ec.remove_mailbox_addresses(uname,
                                                 [address])
                self.logger.info('Removed %s from %s' % 
                        (address, uname))
                # Log a reciept that represents completion of the operation in
                # ChangeLog.
                # TODO: Move this to the caller sometime
                self.ut.log_event_receipt(event, 'exchange:acc_addr_rem')
            except ExchangeException, e:
                self.logger.warn('Can\'t remove %s from %s: %s' % 
                                 (address, uname, e))
                raise EventExecutionException

        elif eit == self.co.entity_group:
            group_spreads = self.ut.get_group_spreads(eid)
            # TODO: Do we need this? Could this happen?
            if self.dg_spread in group_spreads:
                gname, desc = self.ut.get_group_information(eid)
                gname = self.config['distgroup_prefix'] + gname
                try:
                    self.ec.remove_distgroup_addresses(gname, [address])
                    self.logger.info('Removed %s from %s' % 
                            (address, gname))
                    # Log a reciept that represents completion of the operation
                    # in ChangeLog.
                    # TODO: Move this to the caller sometime
                    self.ut.log_event_receipt(event, 'dlgroup:remaddr')
                except ExchangeException, e:
                    self.logger.warn('Can\'t remove %s from %s: %s' % 
                                     (address, gname, e))
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

        @type event: Cerebrum.extlib.db_row.row
        @param event: The event returned from Change- or EventLog
        
        @raises ExchangeException: If all accounts could not be updated.
        """
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
            if not self.mb_spread in self.ut.get_account_spreads(eid):
                # If we wind up here, the user is not supposed to be in Exchange :S
                raise UnrelatedEvent
            addr = self.ut.get_account_primary_email(eid)
            try:
                self.ec.set_primary_mailbox_address(uname, addr)
                self.logger.info('Changing primary address of %s to %s' %
                                 (uname, addr))
                # Log a reciept that represents completion of the operation
                # in ChangeLog.
                # TODO: Move this to the caller sometime
                self.ut.log_event_receipt(event, 'exchange:acc_primaddr')

            except ExchangeException, e:
                self.logger.warn(
                        'Can\'t change primary address of %s to %s: %s' % \
                                 (uname, addr, e))
                raise EventExecutionException
        else:
            # If we can't handle the object type, silently discard it
            raise EntityTypeError
#####
# Group related commands
#####



    @EventDecorator.RegisterHandler(['spread:add'])
    def create_distribution_group(self, event):
        """Event handler for creating distribution groups upon addition of
        spread
        
        @type event: Cerebrum.extlib.db_row.row
        @param event: The event returned from Change- or EventLog
        """
        gname = None
        # TODO: Handle exceptions!
        # TODO: Implicit checking of type. Should it be excplicit?
        added_spread_code = self.ut.unpickle_event_params(event)['spread']
        if added_spread_code == self.dg_spread:
            gname, desc = self.ut.get_group_information(event['subject_entity'])
            gname = self.config['distgroup_prefix'] + gname

            try:
                self.ec.new_distribution_group(gname,
                                               self.config['distgroup_path'])
                self.logger.info('Created distributiongroup %s' % gname)
                self.ut.log_event_receipt(event, 'dlgroup:create')
            except ExchangeException, e:
                self.logger.warn('Could not create group %s: %s' % (gname, e))
                raise EventExecutionException

        

            try:
                self.ec.set_distgroup_address_policy(gname)
                self.logger.debug2('Disabling DG address policy for %s' % gname)
            except ExchangeException, e:
                self.logger.warn(
                        'Could not disable address policy for %s %s' % \
                                (gname, e))
                self.ut.log_event(event, 'exchange:set_ea_policy')

            data = self.ut.get_distgroup_attributes_and_targetdata(
                                                        event['subject_entity'])
            # Only for pure distgroups :)
            if data['roomlist'] == 'F':
                # Set primary address
                try:
                    self.ec.set_distgroup_primary_address(gname,
                                                          data['primary'])
                    self.logger.info('Set primary %s for %s' % (data['primary'],
                                                                gname))
                    self.ut.log_event_receipt(event, 'dlgroup:primary')
                except ExchangeException, e:
                    self.logger.warn('Can\'t set primary %s for %s: %s' % \
                            (data['primary'], gname, e))
# TODO: This won't really work. Not implemented. Fix it somehow
                    # We create another event to set the primary address since
                    # setting it now failed
                    ev_mod = event.copy()
                    ev_mod['subject_entity'], tra, sh, hq, sq = \
                            self.ut.get_email_target_info(
                                        target_entity=event['subject_entity'])
                    self.ut.log_event(ev_mod,
                                        'email_primary_address:add_primary')

                # Set mailaddrs
                try:
                    self.ec.add_distgroup_addresses(gname, data['aliases'])
                    self.logger.info('Set addresses for %s: %s' % \
                                                    (gname,
                                                     str(data['aliases'])))
                    # TODO: More resolution here? We want to mangle the event to
                    # show addresses?
                    self.ut.log_event_receipt(event, 'dlgroup:addaddr')

                except ExchangeException, e:
                    self.logger.warn('Can\'t set addresses %s for %s: %s' % \
                            (str(data['aliases']), gname, e))
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
                                                {'dom_id': info['id'],
                                                 'lp': x[0]})
                        self.ut.log_event(ev_mod, 'email_address:add_address')
                     
                # Set hidden
                try:
                    hide = True if data['hidden'] == 'T' else False
                    self.ec.set_distgroup_visibility(gname, not hide)
                    self.logger.info('Set %s visible: %s' % (gname,
                                                             data['hidden']))
                    self.ut.log_event_receipt(event, 'dlgroup:modhidden')
                except ExchangeException, e:
                    self.logger.warn('Can\'t set visibility for %s: %s' % \
                            (gname, e))
                    ev_mod = event.copy()
                    ev_mod['change_params'] = pickle.dumps(
                                                {'hidden': data['hidden']})
                    self.ut.log_event(ev_mod, 'dlgroup:modhidden')

                # Set manager
                try:
                    self.ec.set_distgroup_manager(gname, data['mngdby_address'])
                    self.logger.info('Set manager of %s to %s' % \
                            (gname, data['mngdby_address']))
                    self.ut.log_event_receipt(event, 'dlgroup:modmanby')
                except ExchangeException, e:
                    self.logger.warn('Can\'t set manager of %s to %s: %s' % \
                                (gname, data['mngdby_address'], e))
                    ev_mod = event.copy()
                    ev_mod['change_params'] = pickle.dumps(
                            {'manby': data['mngdby_address']})
                    self.ut.log_event(ev_mod, 'dlgroup:modmanby')

            # Set join/part restriction
            try:
                self.ec.set_distgroup_member_restrictions(gname,
                                                  join=data['joinrestr'],
                                                  part=data['deprestr'])
                self.logger.info('Set part %s, join %s for %s' % \
                        (data['deprestr'], data['joinrestr'], gname))
                self.ut.log_event_receipt(event, 'dlgroup:modjoinre')
                self.ut.log_event_receipt(event, 'dlgroup:moddepres')
            except ExchangeException, e:
                self.logger.warn('Can\'t set part %s, join %s for %s: %s' % \
                        (data['deprestr'], data['joinrestr'], gname, e))
                ev_mod = event.copy()
                ev_mod['change_params'] = pickle.dumps(
                                    {'joinrestr': data['joinrestr'],
                                    'deprestr': data['deprestr']})
                self.ut.log_event(ev_mod, 'dlgroup:moddepres')
            
            # Only for pure distgroups :)
            if data['roomlist'] == 'F':
                # Set moderation
                enable = True if data['modenable'] == 'T' else False
                try:
                    self.ec.set_distgroup_moderation(gname, enable)
                    self.logger.info('Set moderation on %s to %s' % \
                            (gname, data['modenable']))
# TODO: Receipt for this?
                except ExchangeException, e:
                    self.logger.warn('Can\'t set moderation on %s to %s: %s' % \
                            (gname, data['modenable'], str(e)))
                    ev_mod = event.copy()
                    ev_mod['change_params'] = pickle.dumps(
                                            {'modenable': data['modenable']})
                    self.ut.log_event(ev_mod, 'dlgroup:moderate')
                
                # Set moderator
                try:
                    self.ec.set_distgroup_moderator(gname, data['modby'])
                    self.logger.info('Set moderators %s on %s' % \
                            (data['modby'], gname))
                    # TODO: This correct? CLConstants is a bit strange
                    self.ut.log_event_receipt(event, 'dlgroup:modmodby')
                except ExchangeException, e:
                    self.logger.warn('Can\'t set moderators %s on %s' % \
                            (data['modby'], gname))
                    ev_mod = event.copy()
                    ev_mod['change_params'] = pickle.dumps(
                                            {'modby': data['modby']})
                    self.ut.log_event(ev_mod, 'dlgroup:modmodby')

            tmp_fail = False
            # Set displayname
            try:
                self.ec.set_group_display_name(gname, data['displayname'])
                self.logger.info('Set displayname to %s for %s' % \
                        (data['name'], gname))
            except ExchangeException, e:
                self.logger.warn('Can\'t set displayname to %s for %s: %s' \
                        % (data['name'], gname, e))
                tmp_fail = True

            # Set description
            # TODO: This if ain't needed for distgroups, yes?
            # TODO: Should we rarther pull this from get_group_information?
            if data['description']:
                try:
                    self.ec.set_distgroup_description(gname,
                                                      data['description'])
                    self.logger.info('Set description to %s for %s' % \
                            (data['description'], gname))
                except ExchangeException, e:
                    self.logger.warn('Can\'t set description to %s for %s: %s' \
                            %(data['description'], gname, e))
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
            self.logger.debug2('UnrelatedEvent')
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
            self.logger.debug5('Creating event: Adding %s to %s' % 
                                                        (memb['name'], gname))
            self.ut.log_event(ev_mod, 'e_group:add')


    @EventDecorator.RegisterHandler(['spread:add'])
    def create_security_group(self, event):
        """Event handler for creating security groups upon addition of
        spread
        
        @type event: Cerebrum.extlib.db_row.row
        @param event: The event returned from Change- or EventLog
        """
        gname = None
        # TODO: Handle exceptions!
        # TODO: Should we check the type of the event-target excplicitly?
        added_spread_code = self.ut.unpickle_event_params(event)['spread']
        if added_spread_code == self.sg_spread:
            gname, desc = self.ut.get_group_information(event['subject_entity'])
            gname = self.config['secgroup_prefix'] + gname

            # Create the security group
            try:
                self.ec.new_secgroup(gname, self.config['secgroup_ou'])
                self.logger.info('Created security group %s' % gname)
            except ExchangeException, e:
                self.logger.warn('Could not create security group %s: %s' % \
                        (gname, e))
                raise EventExecutionException
           
            # Set the security groups description if defined
            if desc:
                try:
                    self.ec.set_secgroup_description(gname, desc)
                    self.logger.info('Set description to %s for %s' % \
                            (desc, gname))
                except ExchangeException, e:
                    self.logger.warn('Can\'t set description to %s for %s: %s' \
                            %(desc, gname, e))
                    # Log a "new" event for updating display name and
                    # description We don't mangle the event here, since the
                    # only thing we care about when updating the name or
                    # description is the subject_entity.
                    self.ut.log_event(event, 'entity_name:mod')
        else:
            # TODO: Fix up this comment, it is not the entire truth.
            # If we can't handle the object type, silently discard it
            self.logger.debug2('UnrelatedEvent')
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
            self.logger.debug5('Creating event: Adding %s to %s' % 
                                                        (memb['name'], gname))
            self.ut.log_event(ev_mod, 'e_group:add')


# TODO: split this into two
    @EventDecorator.RegisterHandler(['spread:delete'])
    def remove_group(self, event):
        """Removal of distributiongroup when spread is removed.

        @type event: Cerebrum.extlib.db_row.row
        @param event: The event returned from Change- or EventLog
        """
        removed_spread_code = self.ut.unpickle_event_params(event)['spread']
        if removed_spread_code == self.dg_spread:
            gname, desc = self.ut.get_group_information(event['subject_entity'])
            gname = self.config['distgroup_prefix'] + gname
            try:
                self.ec.remove_distgroup(gname)
                self.logger.info('Removed distrgroup %s' % gname)
                self.ut.log_event_receipt(event, 'dlgroup:remove')
                
            except ExchangeException, e:
                self.logger.warn('Couldn\'t remove distribution group %s' % \
                                  gname)
                raise EventExecutionException
        if removed_spread_code == self.sg_spread:
            gname, desc = self.ut.get_group_information(event['subject_entity'])
            gname = self.config['secgroup_prefix'] + gname
            try:
                self.ec.remove_secgroup(gname)
                self.logger.debug2('Removed secgroup %s' % gname)
            except ExchangeException, e:
                self.logger.warn('Couldn\'t remove security group %s: %s' % \
                                  (gname, e))
                raise EventExecutionException
        if (not self.dg_spread == removed_spread_code) or \
           (not self.sg_spread == removed_spread_code):
            # Silently discard it
            raise UnrelatedEvent


    @EventDecorator.RegisterHandler(['e_group:add'])
    def add_group_member(self, event):
        """Addition of member to group.

        @type event: Cerebrum.extlib.db_row.row
        @param event: The event returned from Change- or EventLog
        """
        # Look up group information (eid and spreads)
        # Look up member for removal
        # Remove from group type according to spread

        # Check to see if we should do something with this member
        try:
            et = self.ut.get_entity_type(event['subject_entity'])
            if not et == self.co.entity_account:
                raise Errors.NotFoundError
            # If we can't find a person with this entity id, we silently
            # discard the event by doing nothing
        except Errors.NotFoundError:
            raise EntityTypeError

        group_spreads = self.ut.get_group_spreads(event['dest_entity'])
        uname = self.ut.get_account_name(event['subject_entity'])
        gname, description = self.ut.get_group_information(event['dest_entity'])
        
        # If the users does not have an AD-spread, it should never end
        # up in a group!
        member_spreads = self.ut.get_account_spreads(event['subject_entity'])

        # Can't stuff that user into the group ;)
        if not self.mb_spread in member_spreads:
            raise UnrelatedEvent
        if not self.ad_spread in member_spreads:
            # TODO: Return? That is NOT sane.
            return

        if self.dg_spread in group_spreads:
            mod_gname = self.config['distgroup_prefix'] + gname
            try:
                self.ec.add_distgroup_member(mod_gname, uname)
                self.logger.info('Added %s to %s' % (uname, mod_gname))
            except ExchangeException, e:
                self.logger.warn('Can\'t add %s to %s: %s' %
                                 (uname, mod_gname, e))
                raise EventExecutionException
        if self.sg_spread in group_spreads:
            mod_gname = self.config['secgroup_prefix'] + gname
            # TODO: Check if secgroup exists
            try:
                self.ec.add_secgroup_member(mod_gname, uname)
                self.logger.info('Added %s to %s' % (uname, mod_gname))
            except ExchangeException, e:
                self.logger.warn('Can\'t add %s to %s: %s' %
                                 (uname, mod_gname, e))
                raise EventExecutionException

        if (not self.dg_spread in group_spreads) or \
           (not self.sg_spread in group_spreads):
            self.logger.error('Unsupported group type for gid=%s!' % \
                              event['subject_entity'])
            # Silently discard it
            raise UnrelatedEvent

    @EventDecorator.RegisterHandler(['e_group:rem'])
    def remove_group_member(self, event):
        """Removal of member from group.

        @type event: Cerebrum.extlib.db_row.row
        @param event: The event returned from Change- or EventLog
        """
        # Look up group information (eid and spreads)
        # Look up member for removal
        # Remove from group type according to spread
        # TODO: We should check if the user to remove exists first.. If it does
        # not, it has allready been removed.. This would probably be smart to
        # do, in order to reduce noise.
        group_spreads = self.ut.get_group_spreads(event['dest_entity'])
        
        # Check to see if we should do something with this member
        try:
            et = self.ut.get_entity_type(event['subject_entity'])
            if not et == self.co.entity_account:
                raise Errors.NotFoundError
            # If we can't find a person with this entity id, we silently
            # discard the event by doing nothing
        except Errors.NotFoundError:
            raise EntityTypeError
        
        uname = self.ut.get_account_name(event['subject_entity'])
        gname, description = self.ut.get_group_information(event['dest_entity'])

        # If the users does not have an AD-spread, we can't remove em. Or can we?
        # TODO: Figure this out
        member_spreads = self.ut.get_account_spreads(event['subject_entity'])

        # Can't remove that user into the group ;)
        if not self.mb_spread in member_spreads:
            raise UnrelatedEvent
        if not self.ad_spread in member_spreads:
            # TODO: Return? That is NOT sane.
            return
        
        if self.dg_spread in group_spreads:
            mod_gname = self.config['distgroup_prefix'] + gname
            try:
                self.ec.remove_distgroup_member(mod_gname, uname)
                self.logger.info('Removed %s from %s' % (uname,
                                                         mod_gname))
            except ExchangeException, e:
                self.logger.warn('Can\'t remove %s from %s: %s' %
                                 (uname, mod_gname, e))
                raise EventExecutionException
        elif self.sg_spread in group_spreads:
            mod_gname = self.config['secgroup_prefix'] + gname
            try:
                self.ec.remove_secgroup_member(mod_gname, uname)
                self.logger.info('Removed %s from %s' % (uname,
                                                         mod_gname))
            except ExchangeException, e:
                self.logger.warn('Can\'t remove %s from %s: %s' %
                                 (uname, mod_gname, e))
                raise EventExecutionException
       
        # TODO: This doesn't result in anything. Will we use it in the future?
        if (not self.dg_spread in group_spreads) or \
           (not self.sg_spread in group_spreads):
            self.logger.error('Unsupported group type for gid=%s!' % \
                              event['subject_entity'])
            # Silently discard it
            raise UnrelatedEvent


    @EventDecorator.RegisterHandler(['dlgroup:modhidden'])
    def set_group_visibility(self, event):
        """Set the visibility of a group.

        @type event: Cerebrum.extlib.db_row.row
        @param event: The event returned from Change- or EventLog
        """
        group_spreads = self.ut.get_group_spreads(event['subject_entity'])
        gname, description = self.ut.get_group_information(
                                                        event['subject_entity'])
        params = self.ut.unpickle_event_params(event)

        if self.dg_spread in group_spreads:
            gname = self.config['distgroup_prefix'] + gname
            
            # Reverse logic, gotta love it!!!11
            show = True if params['hidden'] == 'F' else False
            try:
                self.ec.set_distgroup_visibility(gname, show)
                self.logger.info('Group visibility set to %s for %s' % \
                                    (show, gname))

                # Log a reciept that represents completion of the operation
                # in ChangeLog.
                # TODO: Move this to the caller sometime
                self.ut.log_event_receipt(event, 'dlgroup:modhidden')
            except ExchangeException, e:
                self.logger.warn('Can\'t set hidden to %s for %s: %s' % \
                                    (show, gname, e))
                raise EventExecutionException
        else:
            # TODO: Will we ever arrive here? Log this?
            raise UnrelatedEvent

    @EventDecorator.RegisterHandler(['exchange:set_ea_policy'])
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
                self.logger.info('EAP disabled on %s' % name)
            except ExchangeException, e:
                self.logger.warn('Can\'t disable EAP on account %s: %s' \
                                % (name, e))
                raise EventExecutionException
        elif et == self.co.entity_group:
            name, desc = self.ut.get_group_information(event['subject_entity'])
            name = self.config['distgroup_prefix'] + name
            try:
                self.ec.set_distgroup_address_policy(name)
                self.logger.info('EAP disabled on %s' % name)
            except ExchangeException, e:
                self.logger.warn('Can\'t disable EAP for %s: %s' % (name, e))
        else:
            raise UnrelatedEvent

    @EventDecorator.RegisterHandler(['dlgroup:modmanby'])
    def set_distgroup_manager(self, event):
        """Set a distribution groups manager.

        @type event: Cerebrum.extlib.db_row.row
        @param event: The event returned from Change- or EventLog
        """
        # TODO: More type chacking?
        gname, description = self.ut.get_group_information(
                                                        event['subject_entity'])
        gname = self.config['distgroup_prefix'] + gname
        params = self.ut.unpickle_event_params(event)
        try:
            self.ec.set_distgroup_manager(gname, params['manby'])
            # TODO: Better logging
            self.logger.debug2('Setting manager %s for %s' % \
                                (params['manby'], gname))

            # Log a reciept that represents completion of the operation
            # in ChangeLog.
            # TODO: Move this to the caller sometime
            self.ut.log_event_receipt(event, 'dlgroup:modmanby')
        except ExchangeException, e:
            self.logger.debug2('Failed to set manager %s for %s: %s' % \
                                (params['manby'], gname, e))
            raise EventExecutionException
    
    @EventDecorator.RegisterHandler(['dlgroup:modmodby'])
    def set_distgroup_moderator(self, event):
        """Set a distribution groups moderators.

        @type event: Cerebrum.extlib.db_row.row
        @param event: The event returned from Change- or EventLog
        """
        # TODO: More type checking?
        gname, description = self.ut.get_group_information(
                                                        event['subject_entity'])
        gname = self.config['distgroup_prefix'] + gname
        params = self.ut.unpickle_event_params(event)
        try:
            self.ec.set_distgroup_moderator(gname, params['modby'])
            # TODO: Better logging
            self.logger.debug2('Setting moderators (%s) for %s' % \
                                (params['modby'], gname))
            # Log a reciept that represents completion of the operation
            # in ChangeLog.
            # TODO: Move this to the caller sometime
            self.ut.log_event_receipt(event, 'dlgroup:modmodby')
        except ExchangeException, e:
            self.logger.debug2('Failed to set moderators (%s) on %s: %s' % \
                                (params['modby'], gname, e))
            raise EventExecutionException
    
    @EventDecorator.RegisterHandler(['dlgroup:modenable'])
    def set_distgroup_moderation(self, event):
        """Set moderation enabled or disabled.

        @type event: Cerebrum.extlib.db_row.row
        @param event: The event returned from Change- or EventLog
        """
        # TODO: More type checking?
        gname, description = self.ut.get_group_information(
                                                        event['subject_entity'])
        gname = self.config['distgroup_prefix'] + gname
        params = self.ut.unpickle_event_params(event)
        enable = True if params['modenable'] == 'T' else False
        try:
            self.ec.set_distgroup_moderation(gname, enable)
            self.logger.debug2('Set moderation enabled to %s on %s' % \
                    (str(enable), gname))
        except ExchangeException, e:
            self.logger.debug2(
                    'Failed to set moderation enabled to %s for %s : %s' % \
                            (str(enable), gname, e))
            raise EventExecutionException

    @EventDecorator.RegisterHandler(['dlgroup:moddepres', 'dlgroup:modjoinre'])
    def set_distgroup_restriction(self, event):
        """Set depart and join restrictions on a distribution group.

        @type event: Cerebrum.extlib.db_row.row
        @param event: The event returned from Change- or EventLog
        """
        # TODO: More type checking?
        gname, description = self.ut.get_group_information(
                                                        event['subject_entity'])
        gname = self.config['distgroup_prefix'] + gname
        params = self.ut.unpickle_event_params(event)
        join = part = None
        if params.has_key('deprestr'):
            part = params['deprestr']
        if params.has_key('joinrestr'):
            join = params['joinrestr']
        try:
            self.ec.set_distgroup_member_restrictions(gname, join, part)
            # TODO: Clarify this

            # Log a reciept that represents completion of the operation
            # in ChangeLog.
            # TODO: Move this to the caller sometime
            if join:
                self.ut.log_event_receipt(event, 'dlgroup:modjoinre')
                self.logger.info('Set join restriction to %s for %s' % \
                                    (join, gname))
            if part:
                self.ut.log_event_receipt(event, 'dlgroup:moddepres')
                self.logger.info('Set part restriction to %s for %s' % \
                                    (part, gname))
        except ExchangeException, e:
            self.logger.warn('Can\'t set join/part restriction on %s: %s' % \
                                (gname, e))
            raise EventExecutionException

    # TODO: Is add and del relevant?
    #TODO: This works for description? 
    @EventDecorator.RegisterHandler(['entity_name:add', 'entity_name:mod',
                                     'entity_name:del'])
    def set_group_description_and_name(self, event):
        """Update displayname / description on a group

        @type event: Cerebrum.extlib.db_row.row
        @param event: The event returned from Change- or EventLog
        """
        try:
            et = self.ut.get_entity_type(event['subject_entity'])
            if not et == self.co.entity_group:
                raise Errors.NotFoundError
            # If we can't find a person with this entity id, we silently
            # discard the event by doing nothing
        except Errors.NotFoundError:
            raise EntityTypeError

        failed = False
        group_spreads = self.ut.get_group_spreads(event['subject_entity'])
        # If it is a security group, load info and set display name
        if self.dg_spread in group_spreads:
            attrs = self.ut.get_distgroup_attributes_and_targetdata(
                                                        event['subject_entity'])
            attrs['name'] = self.config['distgroup_prefix'] + attrs['name']

            # Set the display name
            try:
                self.ec.set_group_display_name(attrs['name'],
                                               attrs['displayname'])
                self.logger.info('Set displayname on %s to %s' % \
                        (attrs['name'], attrs['name']))
            except ExchangeException, e:
                self.logger.warn('can\'t set displayname on %s to %s: %s' \
                        % (attrs['name'], attrs['name'], e))
                failed = True

            # Set the description
            try:
                self.ec.set_distgroup_description(attrs['name'],
                                                  attrs['description'])
                self.logger.info('Set description on %s to %s' % \
                        (attrs['name'], attrs['description']))
            except ExchangeException, e:
                self.logger.info('Can\'t set description on %s to %s: %s' % \
                        (attrs['name'], attrs['description'], e))
                failed = True

        # If it is a security group, load info
        elif self.sg_spread in group_spreads:
            name, desc = self.ut.get_group_information(event['subject_entity'])
            name = self.config['secgroup_prefix'] + name
            
            # We don't have displaynames for security groups (yet)

            # Set description
            try:
                self.ec.set_secgroup_description(name, desc)
                self.logger.info('Set description on %s to %s' % \
                                 (name, desc))
            except ExchangeException, e:
                self.logger.info('Can\'t set description on %s to %s: %s' % \
                        (name, desc, e))
                failed = True

            else:
                # TODO: Correct exception? Think about it
                raise UnrelatedEvent

            # If some of the setting operations fail, raise an exception
            # so the event gets resceduled for processing
            if failed:
                raise EventExecutionException
