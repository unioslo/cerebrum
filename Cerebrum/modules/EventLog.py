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

import Cerebrum.ChangeLog
from Cerebrum.modules.ChangeLog import _params_to_db

__version__ = '1.1'


class EventLog(Cerebrum.ChangeLog.ChangeLog):
    """Class used for registring and managing events."""
    # TODO: Fix everything. The entire module is a hack. log_change()
    # should be renamed to log_event, and log_event should be called
    # at the same time as log_change() (maybee).
    # TODO: The method name is kind of a hack.. We should load
    # the EventLog module in a more logical way...
    # TODO: We should not pull in the entire change params into the
    # table.. But we do it for now. We need to do this in order to
    # be able to performe some events, without comapring a humungus
    # ammount of information on a higher level (speed vs. correctness)
    #
    # Don't want to override the Database constructor
    def cl_init(self, **kw):
        super(EventLog, self).cl_init(**kw)
        self.events = []

    # TODO: Rename this to log_event, and make all apropriate callers
    # of log_change compatible. Also, make better docstrings!
    def log_change(self,
                   subject_entity,
                   change_type_id,
                   destination_entity,
                   change_params=None,
                   skip_event=False,
                   **kw):
        """Register events that should be stored into the database.
        """
        # This is kind of hackish. We want to have the possibility not to
        # store some things in the ChangeLog.. When some kind of events
        # partially fail processing (i.e. new-mailbox fails after new-mailbox,
        # but before addresses are set. Should not happen, but it will
        # eventually), we want to generate new events that must be processed.
        super(EventLog, self).log_change(
            subject_entity,
            change_type_id,
            destination_entity,
            change_params=change_params,
            **kw)

        if skip_event:
            return

        self.events.append({
            'change_type_id': change_type_id,
            'subject_entity': subject_entity,
            'destination_entity': destination_entity,
            'change_params': _params_to_db(change_params)
        })

    def clear_log(self):
        """ Remove events in queue for writing. """
        super(EventLog, self).clear_log()
        self.events = []

    def write_log(self):
        """ Commit new events to the event log. """
        super(EventLog, self).write_log()
        # For each event to log..
        for e in self.events:
            # ..find out which systems should get the event..
            targets = self.query("""
                SELECT target_system
                FROM event_to_target
                WHERE event_type = :change_type_id""", e)

            # ..for each of them systems..
            for t in targets:
                # Store the target system
                e.update({'target_sys': t['target_system']})
                # ..fetch a new id for the event..
                eid = int(self.nextval('event_log_seq'))
                # ..store it for "simplicity"..
                e.update({'eid': eid})
                # ..and insert the event into the database..
                self.execute("""
                INSERT INTO [:table schema=cerebrum name=event_log]
                   (event_id, event_type, target_system, subject_entity,
                   dest_entity, change_params)
                   VALUES (:eid, :change_type_id, :target_sys, :subject_entity,
                   :destination_entity, :change_params)""", e)
        self.events = []

    def remove_event(self, event_id, target_system=None):
        """Remove an event from the eventlog. Typically happens when an
        event has completed processing sucessfully.

        :param int event_id: The event id

        :param TargetSystemCode target_system:
            The target system to perform delete on

        :rtype: int
        :return: Affected event id
        """
        params = {'event_id': int(event_id)}
        if target_system:
            params['target_system'] = int(target_system)

        self.query_1("""
            DELETE FROM [:table schema=cerebrum name=event_log]
            WHERE {} RETURNING event_id""".format(
                ' AND '.join(['{} = :{}'.format(k, k) for k in params])),
            params)

    def get_event(self, event_id, target_system=None):
        """Fetch information about an event

        :param int event_id: The event to fetch.

        :param TargetSystemCode target_system:
            The target system to perform select on

        :rtype: Cerebrum.extlib.db_row.row
        :return: One row representing the event
        """
        params = {'event_id': int(event_id)}
        if target_system:
            params['target_system'] = int(target_system)

        return self.query_1("""
            SELECT * FROM event_log
            WHERE %s""" % ' AND '.join(
            ['%s = :%s' % (k, k) for k in params]), params)

    def lock_event(self, event_id):
        """Lock an event for processing.

        :param int event_id: The event to lock.

        :rtype: Cerebrum.extlib.db_row.row
        :return: A database row with the event_id
        """
        return self.query_1(
            """UPDATE event_log
            SET taken_time = now()
            WHERE event_id = :event_id
            AND taken_time IS NULL RETURNING event_id""",
            {'event_id': int(event_id)})

    def get_unprocessed_events(self, target_system, fail_limit=None,
                               failed_delay=None, unpropagated_delay=None,
                               include_taken=False, fetchall=True):
        """Collect IDs of events that has not been processed, or have
        failed processing earlier.

        :param int target_system: The target system to select events from

        :param int fail_limit: Select only events that have failed a number
            of times lower than fail_limit. Default None.

        :param int failed_delay: Select only events that does not have a
            taken_time less than now() - failed_delay.

        :param int unpropagated_delay: Select only events that does not have a
            taken_time, and and tstamp less than now() - unpropagated_delay.

        :param bool include_taken: Wether or not to include events marked for
            processing.

        :param bool fetchall:
            If True, fetch all results. Else, return iterator.

        :rtype: list(Cerebrum.extlib.db_row.row)
        :return: A list of unprocessed database rows
        """
        where = 'target_system = :target_system'
        args = {'target_system': int(target_system)}
        # TODO: Calculate failed_delay on the basis of the number of times
        # previously tried, and a var. Then we can increase the time between
        # each retry. That seems sensible.
        # This would probably neccitate a function. Or do it higher up?
        if fail_limit:
            where += ' AND failed < :failed_limit'
            args['failed_limit'] = fail_limit
        if failed_delay and not unpropagated_delay:
            # OR taken_time IS NULL' % \
            where += " AND (taken_time < [:now] - interval '{:d}s')".format(
                failed_delay)
        elif unpropagated_delay and not failed_delay:
            where += " AND (tstamp < [:now] - interval '{:d}s')".format(
                unpropagated_delay)
        elif unpropagated_delay and failed_delay:
            where += " AND (taken_time < [:now] - interval '{:d}s'".format(
                failed_delay)
            where += " OR tstamp < [:now] - interval '{:d}s')".format(
                unpropagated_delay)
        if not include_taken:
            where += ' AND taken_time IS NULL'

        return self.query("""
            SELECT * FROM event_log
            WHERE {}""".format(where), args, fetchall=fetchall)

    def release_event(self, event_id, target_system=None, increment=True):
        """Release a locked/taken event. Releases typically happens
        when an event fails processing.

        :param int event_id: The event id to release

        :param TargetSystemCode target_system:
            The target system to perform unlock on

        :param bool increment: Whether or not to increment the 'failed' field
            in the database upon release.

        :rtype: int
        :return: The event id
        """
        params = {'event_id': int(event_id)}
        # We check if we should increment the failed column
        if increment:
            inc = ', failed = failed + 1'
        else:
            inc = ''
        if target_system:
            params['target_system'] = int(target_system)
        self.query_1(
            """UPDATE event_log SET taken_time = NULL
            {} WHERE {} RETURNING event_id""".format(
                inc,
                ' AND '.join(['{} = :{}'.format(k, k) for k in params])),
            params)

    ###
    # Utility functions
    ###

    def get_target_stats(self, target_system, fail_limit=10):
        """Collect statistics for a target system.

        :param TargetSystemCode target_system:
            The target system to collect from

        :param int fail_limit:
            Number of failures before it is a permanent failure

        :rtype: dict
        :return: {t_failed, t_locked, total}
        """
        t_locked = self.query_1(
            'SELECT count(*) FROM event_log WHERE taken_time IS NOT NULL'
            ' AND target_system = :target_system',
            {'target_system': int(target_system)})
        t_failed = self.query_1(
            'SELECT count(*) FROM event_log WHERE failed >= :fail_limit'
            ' AND target_system = :target_system',
            {'target_system': int(target_system), 'fail_limit': fail_limit})
        total = self.query_1(
            'SELECT count(*) FROM event_log WHERE'
            ' target_system = :target_system',
            {'target_system': int(target_system)})
        return {'t_locked': t_locked, 't_failed': t_failed, 'total': total}

    def get_failed_and_locked_events(self, target_system, fail_limit=10,
                                     locked=True, fetchall=True):
        """Collect a list of events that have failed permanently,
        or are locked.

        :param TargetSystemCode target_system:
            The target system to collect from

        :param int fail_limit: Number of failures to filter on

        :param bool locked: Return locked rows?

        :rtype: list(tuple)
        :return: [(event_id, event_type, taken_time, failed,)]
        """
        # TODO: Expand me to allow choosing "precision" on the "locked" rows,
        # like selecting only those locked up until 10 hours ago, for example.
        p = {'ts': int(target_system)}
        q = ('SELECT event_id, event_type, taken_time, failed FROM event_log'
             ' WHERE target_system = :ts')
        tmp = []
        if fail_limit:
            tmp += ['failed >= :fail_limit']
            p['fail_limit'] = fail_limit
        if locked:
            tmp += ['taken_time IS NOT NULL']
        if tmp:
            q += ' AND (' + ' OR '.join(tmp) + ')'

        return self.query(q, p, fetchall=fetchall)

    def reset_failed_count(self, event_id):
        """Reset the failed count on an event

        :param int event_id: The event id

        :rtype: int
        :return: Affected event id
        """
        self.query_1(
            """UPDATE event_log SET failed = 0
            WHERE event_id = :id RETURNING event_id""",
            {'id': int(event_id)})

    def reset_failed_counts_for_target_system(self, target_system):
        """Reset the failed counts for all events to a target system where
        failed > 0.

        :param int target_system: The target system

        :rtype: int
        :return: Number of affected events
        """
        self.execute(
            """UPDATE event_log SET failed = 0 WHERE target_system = :ts
            AND failed > 0""",
            {'ts': int(target_system)})
        return self.rowcount

    def search_events(self, id=None, type=None, param=None,
                      from_ts=None, to_ts=None, target_system=None,
                      fetchall=True):
        """Search for events based on a given criteria.

        :param int id: The subject- or dest_entity to search for.
        :param int type: The EventType to search for.
        :param str param: A substring to search for in change_params.
        :param DateTime/str from_ts: Search for events that occoured after this
            timestamp.
        :param DateTime/str to_ts: Search for events that occoured before this
            timestamp.
        :param int target_system: The TargetSystem to search for.
        :param bool fetchall: Wether to return an iterator, or everything.
            Default is everything.
        :rtype: list
        :return: A list of event ids.
        """
        q = "SELECT event_id FROM event_log"
        where = []
        binds = {}
        if id:
            where.append("(subject_entity = :id OR dest_entity = :id)")
            binds['id'] = int(id)
        if type:
            if isinstance(type, (list, tuple, set)):
                where.append("event_type IN ({})".format(
                    ", ".join(map(str, map(int, type)))))
            else:
                where.append("event_type = :type")
                binds['type'] = int(type)
        if target_system:
            where.append("target_system = :target_system")
            binds['target_system'] = int(target_system)
        if from_ts:
            where.append("tstamp > :from_ts")
            binds['from_ts'] = from_ts
        if to_ts:
            where.append("tstamp < :to_ts")
            binds['to_ts'] = to_ts
        if param:
            where.append("change_params LIKE :param")
            binds['param'] = "%{}%".format(param)
        if binds:
            q += " WHERE " + ' AND '.join(where)

        return self.query(q, binds, fetchall=True)

    def get_event_target_type(self, id):
        """Get the destination and subject entitys entity type.

        :param int id: The event id.
        :rtype: dbrow
        :return: The entity type of the destination and subject entity.
        """
        r = {}
        ev = self.get_event(id)
        q = "SELECT entity_type FROM entity_info WHERE entity_id = :eid"
        if ev['subject_entity']:
            r['subject_type'] = self.query_1(q, {'eid': ev['subject_entity']})
        if ev['dest_entity']:
            r['dest_type'] = self.query_1(q, {'eid': ev['dest_entity']})

        return r
