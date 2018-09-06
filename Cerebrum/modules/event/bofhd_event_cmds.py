#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2014-2018 University of Oslo, Norway
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
from collections import defaultdict

import six

import eventconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils import json
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.cmd_param import (Command,
                                              FormatSuggestion,
                                              Parameter,
                                              SimpleString)
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.bofhd.errors import PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings


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
    parent_commands = False
    authz = BofhdAuth

    @classmethod
    def get_help_strings(cls):
        """Definition of the help text for event-related commands."""
        _, _, args = get_help_strings()
        return merge_help_strings(
            ({}, {}, args),
            (HELP_EVENT_GROUP, HELP_EVENT_CMDS, HELP_EVENT_ARGS))

    def _validate_target_system(self, operator, target_sys):
        """Validate that the target system exists."""
        # TODO: Check for perms on target system.
        ts = self.const.TargetSystem(target_sys)
        try:
            # Provoke. See if it exists.
            int(ts)
        except Errors.NotFoundError:
            raise CerebrumError('No such target system: %r' % target_sys)
        return ts

    def _make_constants_human_readable(self, data):
        """Convert dictionary entries known to contain contant codes,
        to human-readable text."""
        constant_keys = ['spread', 'entity_type', 'code', 'affiliation',
                         'src', 'name_variant', 'action', 'level']
        try:
            for key in constant_keys:
                if key in data:
                    value = self.const.human2constant(data[key])
                    if value:
                        data[key] = six.text_type(value)
        except TypeError:
            pass
        return data

    def _parse_search_params(self, *args):
        """Convert string search pattern to a dict."""
        # TODO: Make the param-search handle spaces and stuff?
        params = defaultdict(list)
        for arg in args:
            try:
                key, value = arg.split(':', 1)
            except ValueError:
                # Ignore argument
                continue
            if key == 'type':
                try:
                    cat, typ = value.split(':')
                except ValueError:
                    raise CerebrumError('Search pattern incomplete')
                try:
                    type_code = int(self.clconst.ChangeType(cat, typ))
                except Errors.NotFoundError:
                    raise CerebrumError('EventType does not exist')
                params['type'].append(type_code)
            else:
                params[key] = value
        return params

    def _search_events(self, **params):
        """Find rows matching search params."""
        try:
            return self.db.search_events(**params)
        except TypeError:
            # If the user spells an argument wrong, we tell them that they have
            # done so. They can always type '?' at the pattern-prompt to get
            # help.
            raise CerebrumError('Invalid arguments')
        except self.db.DataError as e:
            # E.g. bogus timestamp
            message = e.args[0].split("\n")[0]
            raise CerebrumError('Database does not approve: ' + message)

    #
    # event stat
    #
    all_commands['event_stat'] = Command(
        ('event', 'stat',),
        TargetSystem(),
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

        fail_limit = eventconf.CONFIG[six.text_type(ts)]['fail_limit']
        return self.db.get_target_stats(ts, fail_limit)

    #
    # event list
    #
    all_commands['event_list'] = Command(
        ('event', 'list',),
        TargetSystem(),
        SimpleString(help_ref='event_list_filter', optional=True),
        fs=FormatSuggestion(
            '%-8d %-35s %-22s %d',
            ('id', 'type', 'taken', 'failed',),
            hdr='%-8s %-35s %-22s %s' % ('Id', 'Type', 'Taken', 'Failed',),),
        perm_filter='is_postmaster')

    def event_list(self, operator, target_sys, args='failed'):
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('No access to event')
        ts = self._validate_target_system(operator, target_sys)

        r = []
        # TODO: Check auth on target-system
        #       Remove perm_filter when this is implemented?
        if args == 'failed':
            fail_limit = eventconf.CONFIG[six.text_type(ts)]['fail_limit']
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
            r.append({
                'id': ev['event_id'],
                'type': six.text_type(self.clconst.map_const(ev['event_type'])),
                'taken': ev['taken_time'],
                'failed': ev['failed']
            })
        return r

    #
    # event force_all
    #
    all_commands['event_force_all'] = Command(
        ('event', 'force_all',),
        TargetSystem(),
        fs=FormatSuggestion('Forced %d events', ('rowcount',)),
        perm_filter='is_postmaster')

    def event_force_all(self, operator, ts):
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('No access to event')
        ts = self._validate_target_system(operator, ts)
        rowcount = self.db.reset_failed_counts_for_target_system(ts)
        return {'rowcount': rowcount}

    #
    # event force
    #
    all_commands['event_force'] = Command(
        ('event', 'force',),
        EventId(),
        fs=FormatSuggestion('Forcing %s', ('state',)),
        perm_filter='is_postmaster')

    def event_force(self, operator, event_id):
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('No access to event')
        try:
            self.db.reset_failed_count(event_id)
            state = True
        except Errors.NotFoundError:
            state = False
        return {'state': 'failed' if not state else 'succeeded'}

    #
    # event unlock
    #
    all_commands['event_unlock'] = Command(
        ('event', 'unlock',),
        EventId(),
        fs=FormatSuggestion('Unlock %s', ('state',)),
        perm_filter='is_postmaster')

    def event_unlock(self, operator, event_id):
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('No access to event')
        try:
            self.db.release_event(event_id, increment=False)
            state = True
        except Errors.NotFoundError:
            state = False
        return {'state': 'failed' if not state else 'succeeded'}

    # event delete
    all_commands['event_delete'] = Command(
        ('event', 'delete',), EventId(),
        fs=FormatSuggestion('Deletion %s', ('state',)),
        perm_filter='is_postmaster')

    def event_delete(self, operator, event_id):
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('No access to event')

        try:
            self.db.remove_event(event_id)
            state = True
        except Errors.NotFoundError:
            state = False
        return {'state': 'failed' if not state else 'succeeded'}

    # event delete_where
    all_commands['event_delete_where'] = Command(
        ('event', 'delete_where',),
        TargetSystem(),
        SimpleString(repeat=True, help_ref='search_pattern'),
        fs=FormatSuggestion(
            'Deleted %s of %s matching events (%s failed/vanished)',
            ('success', 'total', 'failed')),
        perm_filter='is_postmaster')

    def event_delete_where(self, operator, target_sys, *args):
        """Delete events matching a search query.

        :param str target_sys: Target system to search
        :param str args: Pattern(s) to search for.
        """
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('No access to event')

        # TODO: Fetch an ACL of which target systems can be searched by this
        ts = self._validate_target_system(operator, target_sys)

        params = self._parse_search_params(*args)
        if not params:
            raise CerebrumError('Must specify search pattern.')

        params['target_system'] = ts
        event_ids = [row['event_id'] for row in self._search_events(**params)]
        stats = {}
        stats['total'] = len(event_ids)
        stats['success'] = stats['failed'] = 0

        for event_id in event_ids:
            try:
                self.db.remove_event(event_id)
                stats['success'] += 1
            except Errors.NotFoundError:
                stats['failed'] += 1
        return stats

    # event info
    all_commands['event_info'] = Command(
        ('event', 'info',),
        EventId(),
        fs=FormatSuggestion(
            'Event ID:           %d\n'
            'Event type:         %s\n'
            'Target system:      %s\n'
            'Failed attempts:    %d\n'
            'Time added:         %s\n'
            'Time taken:         %s\n'
            'Subject entity:     %s\n'
            'Destination entity: %s\n'
            'Parameters:         %s',
            ('event_id', 'event_type', 'target_system', 'failed',
             'tstamp', 'taken_time',
             'subject_entity', 'dest_entity', 'change_params')
        ),
        perm_filter='is_postmaster')

    def event_info(self, operator, event_id):
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('No access to event')

        try:
            ev = self.db.get_event(event_id)
        except Errors.NotFoundError:
            raise CerebrumError('Error: No such event exists!')

        # For certain keys, convert constants to human-readable representations
        change_params = ev['change_params']
        if change_params:
            change_params = json.loads(ev['change_params'])
            change_params = self._make_constants_human_readable(change_params)
            change_params = repr(change_params)
        else:
            change_params = None

        ret = {
            'event_id': ev['event_id'],
            'event_type': six.text_type(
                self.clconst.map_const(ev['event_type'])),
            'target_system': six.text_type(
                self.const.map_const(ev['target_system'])),
            'failed': ev['failed'],
            'tstamp': ev['tstamp'],
            'taken_time': ev['taken_time'],
            'subject_entity': ev['subject_entity'],
            'dest_entity': ev['dest_entity'],
            'change_params': change_params,
        }

        en = Factory.get('Entity')(self.db)

        # Look up types and names for subject and destination entities
        for key in ('subject_entity', 'dest_entity'):
            if ev[key]:
                try:
                    en.clear()
                    en.find(ev[key])
                    entity_type = six.text_type(
                        self.const.map_const(en.entity_type))
                    entity_name = self._get_entity_name(
                        en.entity_id, en.entity_type)
                    ret[key] = '{} {} (id:{:d})'.format(
                        entity_type, entity_name, en.entity_id)
                except Exception:
                    pass

        return ret

    #
    # event search
    #
    all_commands['event_search'] = Command(
        ('event', 'search',),
        TargetSystem(),
        SimpleString(repeat=True, help_ref='search_pattern'),
        fs=FormatSuggestion(
            '%-8d %-35s %-15s %-15s %-22s %-6d %s',
            ('id', 'type', 'subject_type', 'dest_type', 'taken',
                'failed', 'params'),
            hdr='%-8s %-35s %-15s %-15s %-22s %-6s %s' % (
                'Id', 'Type', 'SubjectType', 'DestinationType', 'Taken',
                'Failed', 'Params'),
        ),
        perm_filter='is_postmaster')

    def event_search(self, operator, target_sys, *args):
        """Search for events in the database.

        :param str target_sys: Target system to search
        :param str args: Pattern(s) to search for.
        """
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('No access to event')

        # TODO: Fetch an ACL of which target systems can be searched by this
        ts = self._validate_target_system(operator, target_sys)

        params = self._parse_search_params(*args)
        if not params:
            raise CerebrumError('Must specify search pattern.')

        params['target_system'] = ts
        event_ids = self._search_events(**params)

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

            change_params = ev['change_params']
            if ev['change_params']:
                change_params = json.loads(ev['change_params'])
                change_params = self._make_constants_human_readable(
                    change_params)

            ret = {
                'id': ev['event_id'],
                'type': six.text_type(
                    self.clconst.map_const(ev['event_type'])),
                'taken': ev['taken_time'],
                'failed': ev['failed'],
                'params': repr(change_params),
                'dest_type': None,
                'subject_type': None,
            }

            if 'dest_type' in types:
                ret['dest_type'] = six.text_type(self.const.map_const(
                    types['dest_type']))
            if 'subject_type' in types:
                ret['subject_type'] = six.text_type(self.const.map_const(
                    types['subject_type']))
            r.append(ret)
        return r


HELP_EVENT_GROUP = {
    'event': "Event related commands",
}

HELP_EVENT_CMDS = {
    'event': {
        'event_stat':
            'Show statistics about the events',
        'event_info':
            'Display an event',
        'event_list':
            'List locked and failed events',
        'event_force':
            'Force processing of a terminally failed event',
        'event_force_all':
            'Force processing of all failed events for a target system',
        'event_unlock':
            'Unlock a previously locked event',
        'event_delete':
            'Delete an event',
        'event_delete_where':
            'Delete events matching search',
        'event_search':
            'Search for events',
    },
}

HELP_EVENT_ARGS = {
    'target_system':
        ['target_system', 'Enter target system (e.g. \'Exchange\')',
         'Enter the target system for this operation'],
    'event_id':
        ['event_id', 'Enter event id',
         'The numerical identifier of an event'],
    'event_list_filter':
        ['event_filter', 'Event filter type',
         "Enter filter type ('failed', 'full')"],
    'search_pattern':
        ['search_pattern', 'Enter search pattern',
         "Patterns that can be used:\n"
         "  id:0                   Matches events where dest- or "
         "subject_entity is set to 0\n"
         "  type:spread:add        Matches events of type spread:add\n"
         "  param:Joe              Matches events where the string"
         " 'Joe' is found in the change params\n"
         "  from_ts:2016-01-01     Matches events from after a "
         "timestamp\n"
         "  to_ts:2016-12-31       Matches events from before a "
         "timestamp\n"
         "In combination, these patterns form a boolean AND\n"
         "expression. Multiple event types forms an OR expression."
         "\nTimestamps can also be 'today', 'yesterday' or precise"
         " to the second."],
}
