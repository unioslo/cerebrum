# encoding: utf-8
#
# Copyright 2017 University of Oslo, Norway
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
""" mod_events database accessor. """

from __future__ import absolute_import

import json
import six

from Cerebrum.DatabaseAccessor import DatabaseAccessor
from .event import Event, EventType, EntityRef


class EventsAccessor(DatabaseAccessor):
    """ Database access to the event tables. """

    def create_event(self, event_type, subject_id, subject_type, subject_ident,
                     schedule=None, data=None):
        """ Store a new event.

        :param str event_type:
            The type of change that created this event.

        :param int subject_id:
            The entity_id of the altered object.

        :param str subject_ident:
            The identifier of the subject (e.g. entity_name, ext_id or similar)

        :param str subject_type:
            The entity_type of the altered object.

        :param DateTime schedule:
            When this event should be issued (default: None, indicates wihtout
            delay).

        :param **data:
            Additional JSON-serializable data to bundle with this event.

        """
        binds = dict()
        query = """
        INSERT INTO [:table schema=cerebrum name=events]
          (event_id, event_type, schedule,
           subject_id, subject_ident, subject_type,
           event_data)
        VALUES
          (:event_id, :event_type, :schedule,
           :subject_id, :subject_ident, :subject_type,
           :event_data)
        RETURNING event_id
        """

        binds['event_id'] = int(self.nextval('events_seq'))
        binds['event_type'] = six.text_type(event_type)
        binds['schedule'] = schedule
        binds['subject_id'] = int(subject_id)
        binds['subject_ident'] = six.text_type(subject_ident)
        binds['subject_type'] = six.text_type(subject_type)
        binds['event_data'] = json.dumps(data)

        return self.query_1(query, binds)

    def get_event(self, event_id):
        return self.query_1(
            """
            SELECT * FROM [:table schema=cerebrum name=events]
            WHERE event_id = :event_id
            """,
            {'event_id': int(event_id)})

    def delete_event(self, event_id):
        return self.query_1(
            """
            DELETE FROM [:table schema=cerebrum name=events]
            WHERE event_id = :event_id
            RETURNING event_id
            """,
            {'event_id': int(event_id)})

    def lock_event(self, event_id):
        """Lock an event for processing.

        :param int event_id: The event to lock.

        :rtype: Cerebrum.extlib.db_row.row
        :return: A database row with the event_id
        """
        return self.query_1(
            """
            UPDATE [:table schema=cerebrum name=events]
            SET taken_time = now()
            WHERE event_id = :event_id
            AND taken_time IS NULL
            RETURNING event_id
            """,
            {'event_id': int(event_id)})

    def release_event(self, event_id):
        """Release a locked/taken event.

        Releases typically happens when an event fails processing.

        :param int event_id:
            The event id to release

        :rtype: int
        :return: The event id
        """
        self.query_1(
            """
            UPDATE [:table schema=cerebrum name=events]
            SET taken_time = NULL
            WHERE event_id = :event_id
            RETURNING event_id
            """,
            {'event_id': int(event_id)})

    def fail_count_inc(self, event_id):
        """ Increment the failed count on an event

        :param int event_id: The event id

        :rtype: int
        :return: Affected event id
        """
        self.query_1(
            """
            UPDATE [:table schema=cerebrum name=events]
            SET failed = failed + 1
            WHERE event_id = :event_id
            RETURNING event_id
            """,
            {'event_id': int(event_id)})

    def fail_count_reset(self, event_id):
        """Reset the failed count on an event

        :param int event_id: The event id

        :rtype: int
        :return: Affected event id
        """
        return self.query_1(
            """
            UPDATE [:table schema=cerebrum name=events]
            SET failed = 0
            WHERE event_id = :event_id
            RETURNING event_id
            """,
            {'event_id': int(event_id)})

    def get_unprocessed(
            self,
            fail_limit=None,
            failed_delay=None,
            unpropagated_delay=None,
            include_taken=False,
            fetchall=True):
        """ Collect events that has not been processed.

        :param int fail_limit:
            Select only events that have failed a number of times lower than
            fail_limit. Default None.

        :param int failed_delay:
            Select only events that has been taken at least `failed_delay`
            seconds ago.

        :param int unpropagated_delay:
            Select only events that are at least `unpropagated_delay` seconds
            old.

        :param bool include_taken:
            Wether or not to include events marked for processing.

        :param bool fetchall:
            If True, fetch all results. Else, return iterator.

        :return: A sequence of unprocessed database rows
        """
        query_fmt = """
        SELECT * FROM [:table schema=cerebrum name=events]
        {where!s}
        """
        binds = dict()
        criteria = list()

        if fail_limit:
            criteria.append('failed < :failed_limit')
            binds['failed_limit'] = int(fail_limit)

        def _sql_timedelta(seconds):
            # Make an SQL `seconds` ago DATETIME expression.
            return "[:now] - interval '{:d}s'".format(int(seconds))

        if unpropagated_delay is not None and failed_delay is not None:
            criteria.append(
                '(taken_time < {!s} OR timestamp < {!s})'.format(
                    _sql_timedelta(failed_delay),
                    _sql_timedelta(unpropagated_delay)))
        elif failed_delay is not None:
            criteria.append(
                '(taken_time < {!s})'.format(
                    _sql_timedelta(failed_delay)))
        elif unpropagated_delay is not None:
            criteria.append(
                '(timestamp < {!s})'.format(
                    _sql_timedelta(unpropagated_delay)))

        if not include_taken:
            criteria.append('taken_time IS NULL')

        where = "WHERE " + " AND ".join(criteria) if criteria else ""

        return self.query(
            query_fmt.format(where=where),
            binds,
            fetchall=fetchall)


def from_row(row):
    """ Initialize object from a dbrow-like dict. """
    event_type = EventType.get_verb(row['event_type'])
    init = {'subject': EntityRef(row['subject_id'],
                                 row['subject_type'],
                                 row['subject_ident']),
            'timestamp': row['timestamp'],
            'scheduled': row['schedule'], }

    if row['event_data']:
        event_data = json.loads(row['event_data'])
    else:
        event_data = dict()

    init['objects'] = [EntityRef(o['object_id'],
                                 o['object_type'],
                                 o['object_ident'])
                       for o in event_data.get('objects', [])]

    for keyword in ('attributes', 'context'):
        init[keyword] = event_data.get(keyword) or None

    return Event(event_type, **init)
