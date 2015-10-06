#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2014-2015 University of Oslo, Norway
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

from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum import Errors

from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.cmd_param import Command, Parameter, \
    FormatSuggestion, SimpleString
from Cerebrum.modules.bofhd.errors import PermissionDenied

import eventconf


# Event spesific params
class TargetSystem(Parameter):
    """Parameter type used for carrying target system names to commands."""

    _type = 'targetSystem'
    _help_ref = 'target_system'


class EventId(Parameter):
    """Parameter type used for carrying event ids to commands."""

    _type = 'eventId'
    _help_ref = 'event_id'


class BofhdExtension(BofhdCommandBase):
    """Commands used for managing and inspecting events."""

    all_commands = {}

    def __init__(self, server):
        super(BofhdExtension, self).__init__(server)
        self.ba = BofhdAuth(self.db)

    def get_help_strings(self):
        """Definition of the help text for event-related commands."""
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
                'event_search': 'Search for events'
            },
        }

        arg_help = {
            'target_system': [
                'target_system',
                'Target system (i.e. \'Exchange\')',
                'Enter the target system for this operation'],
            'event_id': [
                'event_id',
                'Event Id',
                'The numerical identificator of an event'],
            'search_pattern': [
                'search_pattern',
                'Search pattern',
                'Patterns that can be used:\n'
                '  id:0             Returns all events where dest- or '
                'subject_entity is set to 0\n'
                '  type:spread:add  Returns all events of type spread:add\n'
                '  param:Joe        Returns all events where the string "Joe" '
                'is found in the change params\n'
                'In combination, these patterns form a boolean AND expression']
        }

        return (group_help, command_help,
                arg_help)

    # Validate that the target system exists, and that the operator is
    # allowed to perform operations on it.
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
              ('t_failed', 't_locked', 'total',),), ]),
        perm_filter='is_postmaster')

    def event_stat(self, operator, target_sys):
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('No access to event')
        ts = self._validate_target_system(operator, target_sys)

        fail_limit = eventconf.CONFIG[str(ts)]['fail_limit']
        return self.db.get_target_stats(ts, fail_limit)

    # event list
    all_commands['event_list'] = Command(
        ('event', 'list',), TargetSystem(), SimpleString(optional=True),
        fs=FormatSuggestion(
            '%-8d %-28s %-25s %d',
            ('id', 'type', 'taken', 'failed',),
            hdr='%-8s %-28s %-25s %s' % ('Id', 'Type', 'Taken', 'Failed',),),
        perm_filter='is_postmaster')

    def event_list(self, operator, target_sys, args='failed'):
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('No access to event')
        ts = self._validate_target_system(operator, target_sys)

        r = []
        # TODO: Check auth on target-system
        #       Remove perm_filter when this is implemented?
        if args == 'failed':
            fail_limit = eventconf.CONFIG[str(ts)]['fail_limit']
            locked = True
        elif args == 'full':
            fail_limit = None
            locked = False
        else:
            return []

        for ev in self.db.get_failed_and_locked_events(
                target_system=ts,
                fail_limit=fail_limit,
                locked=locked):
            r += [{
                'id': ev['event_id'],
                # TODO: Change this when we create TargetType()
                'type': str(self.const.ChangeType(ev['event_type'])),
                'taken': str(ev['taken_time']).replace(' ', '_'),
                'failed': ev['failed']
            }]
        return r

    # event force
    all_commands['event_force'] = Command(
        ('event', 'force',), TargetSystem(), EventId(),
        fs=FormatSuggestion('Forcing %s', ('state',)),
        perm_filter='is_postmaster')

    def event_force(self, operator, target_sys, id):
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('No access to event')
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
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('No access to event')
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
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('No access to event')
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
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('No access to event')
        # TODO: Add handlers for printing out different events in a pretty manner
        ts = self._validate_target_system(operator, target_sys)
        try:
            ev = self.db.get_event(id, target_system=ts)
        except Errors.NotFoundError:
            raise CerebrumError('Error: No such event exists!')
        return {'event': str(ev)}

    # event search
    all_commands['event_search'] = Command(
        ('event', 'search',), SimpleString(repeat=True,
                                           help_ref='search_pattern'),
        fs=FormatSuggestion(
            '%-8d %-35s %-15s %-15s %-25s %-6d %s',
            ('id', 'type', 'subject_type', 'dest_type', 'taken',
                'failed', 'params'),
            hdr='%-8s %-35s %-15s %-15s %-25s %-6s %s' % ('Id',
                                                          'Type',
                                                          'SubjectType',
                                                          'DestinationType',
                                                          'Taken',
                                                          'Failed',
                                                          'Params'),
        ),
        perm_filter='is_postmaster')

    def event_search(self, operator, *args):
        """Search for events in the database.

        :param str search_str: A pattern to search for.
        """
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('No access to event')
        # TODO: Fetch an ACL of which target systems can be searched by this
        # TODO: Make the param-search handle spaces and stuff?
        # operator
        params = {}
        # Parse search patterns
        for arg in args:
            tmp = arg.split(':', 1)
            try:
                if tmp[0] == 'type':
                    try:
                        cat, typ = tmp[1].split(':')
                    except ValueError:
                        raise CerebrumError('Search pattern incomplete')
                    try:
                        type_code = int(self.const.ChangeType(cat, typ))
                    except Errors.NotFoundError:
                        raise CerebrumError('EventType does not exist')
                    params['type'] = type_code
                else:
                    params[tmp[0]] = tmp[1]
            except IndexError:
                # We just pass on, won't regard the param.
                pass

        # Raise if we do not have any search patterns
        if not params:
            raise CerebrumError('Must specify search pattern.')

        # Fetch matching event ids
        try:
            event_ids = self.db.search_events(**params)
        except TypeError:
            # If the user spells an argument wrong, we tell them that they have
            # done so. They can always type '?' at the pattern-prompt to get
            # help.
            raise CerebrumError('Invalid arguments')

        # Fetch information about the event ids, and present it to the user.
        r = []
        for event_id in event_ids:
            ev = self.db.get_event(event_id['event_id'])
            try:
                types = self.db.get_event_target_type(event_id['event_id'])
            except Errors.NotFoundError:
                # If we wind up here, both the subject- or destination-entity
                # has been deleted, or the event does not carry information
                # about a subject- or destination-entity.
                types = []

            tmp = {'id': ev['event_id'],
                   # TODO: Change this when we create TargetType()
                   'type': str(self.const.ChangeType(ev['event_type'])),
                   'taken': str(ev['taken_time']).replace(' ', '_'),
                   'failed': ev['failed'],
                   'params': repr(ev['change_params'])
                   }

            if 'dest_type' in types:
                tmp['dest_type'] = str(self.const.EntityType(
                    types['dest_type']))
            else:
                tmp['dest_type'] = None

            if 'subject_type' in types:
                tmp['subject_type'] = str(self.const.EntityType(
                    types['subject_type']))
            else:
                tmp['subject_type'] = None
            r.append(tmp)
        return r
