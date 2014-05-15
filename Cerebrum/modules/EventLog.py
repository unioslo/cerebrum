# -*- coding: iso-8859-1 -*-
# Copyright 2013 University of Oslo, Norway
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

import cerebrum_path
from Cerebrum.modules import ChangeLog

import pickle

__version__='1.0'

class EventLog(object):
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
    def cl_init(self, change_by=None, change_program=None):
        self.events = []
        super(EventLog, self).cl_init(change_by, change_program)

    # TODO: Rename this to log_event, and make all apropriate callers
    # of log_change compatible. Also, make better docstrings!
    def log_change(self, subject_entity, change_type_id,
                   destination_entity, change_params=None,
                   change_by=None, change_program=None,
                   event_only=False,change_only=False):
        """Register events that should be stored into the database.
        """
        # This is kind of hackish. We want to have the possibility not to
        # store some things in the ChangeLog.. When some kind of events
        # partially fail processing (i.e. new-mailbox fails after new-mailbox,
        # but before addresses are set. Should not happen, but it will
        # eventually), we want to generate new events that must be processed.
        if not event_only or change_only:
            super(EventLog, self).log_change(subject_entity, change_type_id,
                                             destination_entity, change_params,
                                             change_by, change_program)
        if not change_only:
            # TODO: We call dumps.. UTF?
            self.events.append({'change_type_id': change_type_id,
                                'subject_entity': subject_entity,
                                'destination_entity': destination_entity,
                                'change_params': pickle.dumps(change_params)})

    def rollback_log(self):
        """Remove events in queue for writing.
        """
        super(EventLog, self).rollback_log()
        self.events = []

    def commit_log(self):
        """Commit new events to the event log.
        """
        super(EventLog, self).commit_log()
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

        @type event_id: int
        @param event_id: The events ID
        
        @type target_system: TargetSystemCode
        @param target_system: The target-system to perform delete on
        """
        params = {'event_id': int(event_id)}
        if target_system:
            params['target_system'] = int(target_system)

        self.query_1("""
        DELETE FROM [:table schema=cerebrum name=event_log]
        WHERE %s RETURNING event_id""" % \
                ' AND '.join(['%s = :%s' % (k,k) for k in params]),
                params)

    def get_event(self, event_id, target_system=None):
        """Fetch information about an event

        @type event_id: int
        @param event_id: The event to fetch.

        @type target_system: TargetSystemCode
        @param target_system: The target-system to perform select on

        @rtype: Cerebrum.extlib.db_row.row
        @return: One row representing the event
        """
        params = {'event_id': int(event_id)}
        if target_system:
            params['target_system'] = int(target_system)

        return self.query_1("""
            SELECT * FROM event_log
            WHERE %s""" %
                ' AND '.join(['%s = :%s' % (k,k) for k in params]),
                params)
        
    def lock_event(self, event_id):
        """Lock an event for processing.

        @type event_id: int
        @param event_id: The event to lock.
        
        @rtype: Cerebrum.extlib.db_row.row
        @return: A DB-row with the event_id
        """
        # TODO: Verify and test
        return self.query_1("""
            UPDATE event_log
            SET taken_time = now()
            WHERE event_id = :event_id
            AND taken_time IS NULL RETURNING event_id""",
            {'event_id': int(event_id)})


    # TODO: Rewrite this so it does not lock events, only collect
    # the IDs of old and unprocessed events
    def get_unprocessed_events(self, target_system, fail_limit=None,
                               failed_delay=None, unpropagated_delay=None,
                               include_taken=False, fetchall=True):
        """Collect IDs of events that has not been processed, or have
        failed processing earlier.

        @type target_system: int
        @param target_system: The target system to select events from
        
        @type fail_limit: int
        @param fail_limit: Select only events that have failed a number
            of times lower than fail_limit. Default None.

        @type failed_delay: int
        @param failed_delay: Select only events that does not have a taken_time
            less than now() - failed_delay.
        
        @type unpropagted_delay: int
        @param unpropagated_delay: Select only events that does not have a
            taken_time, and and tstamp less than now() - unpropagated_delay.

        @type include_taken: bool
        @param include_taken: Wether or not to include events marked for
            processing.

        @type fetchall: bool
        @param fetchall: If True, fetch all results. Else, return iterator.
        
        @rtype: list(Cerebrum.extlib.db_row.row)
        @return: A list of unprocessed DB-rows
        """
        filter = 'target_system = :target_system'
        args = {'target_system': int(target_system)}
        # TODO: Make this pretty!!!111
        # TODO: Calculate failed_delay on the basis of the number of times previously tried,
        # and a var. Then we can increase the time between each retry. That seems sensible.
        # This would probably neccitate a function. Or do it higher up?
        if fail_limit:
            filter += ' AND failed < :failed_limit'
            args['failed_limit'] = fail_limit
        if failed_delay and not unpropagated_delay:
            # OR taken_time IS NULL' % \
            filter += ' AND (taken_time < [:now] - interval \'%d seconds\'' % \
                    failed_delay
        elif unpropagated_delay and not failed_delay:
            filter += ' AND tstamp < [:now] - interval \'%d seconds\'' % \
                    unpropagated_delay
        elif unpropagated_delay and failed_delay:
            filter += ' AND (taken_time < [:now] - interval \'%d seconds\'' % \
                    failed_delay
            filter += ' OR tstamp < [:now] - interval \'%d seconds\')' % \
                    unpropagated_delay
        if not include_taken:
            filter += ' AND taken_time IS NULL'
        
        return self.query("""
            SELECT * FROM event_log
            WHERE %s""" % filter,
            args,
            fetchall=fetchall)

    def release_event(self, event_id, target_system=None, increment=True):
        """Release a locked/taken event. Releases typically happens
        when an event fails processing.

        @type event_id: int
        @param event_id: The events id.
        
        @type target_system: TargetSystemCode
        @param target_system: The target-system to perform unlock on

        @type increment: bool
        @param increment: wether or not to increment the 'failed' field
            in the database upon release.
        """
        params = {'event_id': int(event_id)}
        # We check if we should increment the failed-column
        if increment:
            inc = ', failed = failed + 1'
        else:
            inc = ''
        if target_system:
            params['target_system'] = int(target_system)
        self.query_1("""
            UPDATE event_log
            SET taken_time = NULL
            %s
            WHERE %s RETURNING event_id""" % \
                    (inc, ' AND '.join(['%s = :%s' % (k,k) for k in params])),
            params)



# TODO: Should this really be here? Should it be in a supplemental API?
###
# Utility functions for bofhd-tools
###

    def get_target_stats(self, target_system, fail_limit=10):
        """Collect statistics for a target-system.

        @type target_system: TargetSystemCode
        @param target_system: The target-system to collect from

        @type fail_limit: int
        @param fail_limit: Number of failures before it is a permanent failure

        @rtype: dict
        @return: {t_failed, t_locked, total}
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
        """Collect a list of events that have failed permanently, or are locked.

        @type target_system: TargetSystemCode
        @param target_system: The target-system to collect from

        @type fail_limit: int
        @param fail_limit: Number of failures to filter on

        @type locked: bool
        @param locked: Return locked rows?

        @rtype: list(tuple)
        @return: [(event_id, event_type, taken_time, failed,)]
        
        """
        # TODO: Expand me to allow choosing "presicion" on the "locked" rows,
        # like selecting only those locked up until 10 hours ago, for example.
        p = {'ts': int(target_system)}
        q = 'SELECT event_id, event_type, taken_time, failed FROM event_log' + \
                ' WHERE target_system = :ts'
        tmp = []
        if fail_limit:
            tmp += [ 'failed >= :fail_limit']
            p['fail_limit'] = fail_limit
        if locked:
            tmp += ['taken_time IS NOT NULL']
        if tmp:
            q += ' AND ' + ' OR '.join(tmp)

        return self.query(q, p, fetchall=fetchall)

    def decrement_failed_count(self, target_system, id):
        """Decrement the failed count on a row
        
        @type target_system: TargetSystemCode
        @param target_system: The target-system to collect from

        @type id: int
        @param id: The row id to do this in
        """
        self.query_1(
                'UPDATE event_log SET failed = failed - 1 WHERE event_id = :id'
                ' AND target_system = :ts RETURNING event_id',
                {'id': int(id), 'ts': int(target_system)})

    def search_events(self, id=None, type=None, param=None,
                      from_ts=None, to_ts=None, fetchall=True):
        """Search for events based on a given criteria.

        :param int id: The subject- or dest_entity to search for.
        :param int type: The EventType to search for.
        :param str param: A substring to search for in change_params.
        :param DateTime from_ts: Search for events that occoured after this
            timestamp.
        :param DateTime to_ts: Search for events that occoured before this
            timestamp.
        :param bool fetchall: Wether to return an iterator, or everything.
            Default is everything.
        :rtype: list
        :return: A list of event ids.
        """
        q = "SELECT event_id FROM event_log"
        tmp_q = []
        parm = {}
        if id:
            tmp_q.append("(subject_entity = :id OR dest_entity = :id)")
            parm['id'] = int(id)
        if type:
            tmp_q.append("event_type = :type")
            parm['type'] = int(type)
        if param:
            tmp_q.append("change_params LIKE :param")
            parm['param'] = "%%%s%%" % param
        if parm:
            q += " WHERE "
            q += ' AND '.join(tmp_q)

        return self.query(q, parm, fetchall=True)

    def get_event_target_type(self, id):
        """Get the destination and subject entitys entity type.

        :param int id: The events id.
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
