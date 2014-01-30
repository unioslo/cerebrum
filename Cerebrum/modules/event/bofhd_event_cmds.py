#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2014 University of Oslo, Norway
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

"""Commands used for listing and managing events."""

from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum import Utils
from Cerebrum import Errors

from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.cmd_param import Command, Parameter, \
        FormatSuggestion

import eventconf

# Event spesific params
class TargetSystem(Parameter):
    _type = 'targetSystem'
    _help_ref = 'target_system'

class EventId(Parameter):
    _type = 'eventId'
    _help_ref = 'event_id'

class BofhdExtension(BofhdCommandBase):
    all_commands = {}

    def __init__(self, server):
        super(BofhdExtension, self).__init__(server)
        self.ba = BofhdAuth(self.db)

    def get_help_strings(self):
        group_help = {
            'event': "Event related commands",
            }

        # The texts in command_help are automatically line-wrapped, and should
        # not contain \n
        command_help = {
            'event': {
                'event_stat': 'Show statistics about the events',
                'event_info': 'Display an event',
                'event_list': 'List locked and failed events',
                'event_force': 'Force processing of a terminally failed event',
                'event_unlock': 'Unlock a previously locked event',
                'event_delete': 'Delete an event',
            },
        }

        arg_help = {
            'target_system':
                ['target_system',
                 'Target system (i.e. \'Exchange\')',
                 'Enter the target system for this operation'],
            'event_id':
                ['event_id',
                 'Event Id',
                 'The numerical identificator of an event'],
        }
        
        return (group_help, command_help,
                arg_help)

    # Validate that the target system exists, and that the operator is
    # allowed to perfor operations on it.
    def _validate_target_system(self, operator, target_sys):
        # TODO: Chack for perms on target system.
        ts = self.const.TargetSystem(target_sys)
        try:
            # Provoke. See if it exists.
            int(ts)
        except Errors.NotFoundError:
            raise CerebrumError('No such target-system: %s' % target_sys)
        return ts



    # event stat
    all_commands['event_stat'] = Command(
            ('event', 'stat',), TargetSystem(),
                fs=FormatSuggestion(
                    [('Total failed: %d\n'
                      'Total locked: %d\n'
                      'Total       : %d',
                        ('t_failed', 't_locked', 'total',),),]
                ),
                perm_filter='is_postmaster'
    )
    def event_stat(self, operator, target_sys):
        ts = self._validate_target_system(operator, target_sys)
        
        fail_limit = eventconf.CONFIG[str(ts)]['fail_limit']
        return self.db.get_target_stats(ts, fail_limit)

    # event list
    all_commands['event_list'] = Command(
            ('event', 'list',), TargetSystem(),
                fs=FormatSuggestion(
                    '%-8d %-28s %-25s %d',
                        ('id', 'type', 'taken', 'failed',),
                    hdr='%-8s %-28s %-25s %s' % ('Id', 'Type',
                                                 'Taken', 'Failed',)
                                    ,),
                                    perm_filter='is_postmaster')
    def event_list(self, operator, target_sys):
        ts = self._validate_target_system(operator, target_sys)
        
        r = []
        # TODO: Check auth on target-system
        #       Remove perm_filter when this is implemented?
        fail_limit = eventconf.CONFIG[str(ts)]['fail_limit']
        for ev in self.db.get_failed_and_locked_events(target_system=ts,
                                                       fail_limit=fail_limit,
                                                       locked=True):
            tmp = {'id': ev['event_id'],
                    # TODO: Change this when we create TargetType()
                   'type': str(self.const.ChangeType(ev['event_type'])),
                   'taken': str(ev['taken_time']).replace(' ', '_'),
                   'failed': ev['failed']
                  }
            r += [tmp]
        return r

    # event force
    all_commands['event_force'] = Command(
            ('event', 'force',), TargetSystem(), EventId(),
            fs=FormatSuggestion('Forcing %s', ('state',)),
            perm_filter='is_postmaster')
    def event_force(self, operator, target_sys, id):
        ts = self._validate_target_system(operator, target_sys)

        try:
            self.db.decrement_failed_count(ts, id)
            state = True
        except Errors. NotFoundError:
            state = False
        return {'state': 'failed' if not state else 'succeeded'}

    # event unlock
    all_commands['event_unlock'] = Command(
            ('event', 'unlock',), TargetSystem(), EventId(),
            fs=FormatSuggestion('Unlock %s', ('state',)),
                perm_filter='is_postmaster')
    def event_unlock(self, operator, target_sys, id):
        ts = self._validate_target_system(operator, target_sys)

        try:
            self.db.release_event(id, target_system=ts, increment=False)
            state = True
        except Errors.NotFoundError:
            state = False
        return {'state': 'failed' if not state else 'succeeded'}

    # event delete
    all_commands['event_delete'] = Command(
            ('event', 'delete',), TargetSystem(), EventId(),
            fs=FormatSuggestion('Deleted %s', ('state',)),
            perm_filter='is_postmaster')
    def event_delete(self, operator, target_sys, id):
        ts = self._validate_target_system(operator, target_sys)

        try:
            self.db.remove_event(id, target_system=ts)
            state = True
        except Errors.NotFoundError:
            state = False
        return {'state': 'failed' if not state else 'succeeded'}

    # event info
    all_commands['event_info'] = Command(
            ('event', 'info',), TargetSystem(), EventId(),
            fs=FormatSuggestion('%s', ('event',)),
            perm_filter='is_postmaster')
    def event_info(self, operator, target_sys, id):
        # TODO: Add handlers for printing out different events in a pretty manner
        ts = self._validate_target_system(operator, target_sys)
        try:
            ev = self.db.get_event(id, target_system=ts)
        except Errors.NotFoundError:
            raise CerebrumError('Error: No such event exists!')
        return {'event': str(ev)}

