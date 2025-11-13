# -*- coding: utf-8 -*-
#
# Copyright 2003-2025 University of Oslo, Norway
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
"""
Proccess and tag events from changelog.

This module adds a handler that can keep track of *processed* change ids from
:mod:`Cerebrum.modules.ChangeLog`, for a given *change key*.

Scripts that needs sequential processing of changes, can choose a unique
*change key*, and then request unprocessed events (change log records) from the
:class:`.CLHandler` defined in this module.

Each processed change should be *confirmed* after processing.  The CLHandler
will then keep track of (ranges of) confirmed change ids for each given *change
key*, which will omit them from future requests for unprocessed changes.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import itertools
import string
from Cerebrum.DatabaseAccessor import DatabaseAccessor


_VALID_CHANGE_KEY_CHARS = frozenset(
    string.ascii_letters + string.digits + "-_."
)


def validate_change_key(value):
    """ Validate a change key.  """
    # This needs be be called when adding a new change handler range for a
    # *change key*.  It's mostly here to give a better error message whenever a
    # given change key is too long (db constraint), but also to prevent weird
    # change keys.
    if set(value) - _VALID_CHANGE_KEY_CHARS:
        raise ValueError("invalid change key: " + repr(value))
    if len(value) > 20 or len(value) < 1:
        raise ValueError("invalid change key: " + repr(value))
    return value


def get_all_ranges(db):
    """ Get the full change handler table. """
    return db.query(
        """
          SELECT evthdlr_key, first_id, last_id
          FROM [:table schema=cerebrum name=change_handler_data]
          ORDER BY evthdlr_key, first_id, last_id
        """
    )


def get_ranges_for_key(db, key):
    """ Get all id ranges handled by a given change *key*.  """
    return [
        (int(row['first_id']), int(row['last_id']))
        for row in db.query(
            """
              SELECT first_id, last_id
              FROM [:table schema=cerebrum name=change_handler_data]
              WHERE evthdlr_key=:key
              ORDER BY first_id, last_id
            """,
            {'key': key},
        )
    ]


def clear_ranges_for_key(db, key):
    return db.query(
        """
          DELETE FROM [:table schema=cerebrum name=change_handler_data]
          WHERE evthdlr_key=:key
          RETURNING evthdlr_key, first_id, last_id
        """,
        {'key': key},
    )


def add_range_for_key(db, key, first_id, last_id):
    return db.query_1(
        """
          INSERT INTO [:table schema=cerebrum name=change_handler_data]
            (evthdlr_key, first_id, last_id)
          VALUES
            (:key, :first, :last)
          RETURNING
            evthdlr_key, first_id, last_id
        """,
        {
            'key': validate_change_key(key),
            'first': int(first_id),
            'last': int(last_id),
        },
    )


def _ranges_to_limits(ranges):
    """
    Convert an iterable of ranges to an iterable of limits.

    A range is a tuple with a (first, last) value, inclusive.  Limits are the
    inverse - the search terms for e.g.  `ChangeLog.get_log_events()` to get
    all ids that *aren't* covered by a range.
    """
    prev = -1
    for first_id, last_id in sorted(ranges):
        if prev < first_id - 1:
            yield (prev + 1, first_id - 1)
        prev = last_id

    yield (prev + 1, None)


class CLHandler(DatabaseAccessor):
    """
    Handle changes for a given change key.

    CLHandler provides methods for update notifications when data
    is changed in Cerebrum using the ChangeLog.

    A "change-key" is used to keep track of events to receive and process.  To
    process any unprocessed changes for a given key:
    ::

        handler = CLHandler(database)
        change_types = <relevant change type codes>
        for change_id in handler.get_events("my-key", change_types):
            if handle_event(database, change_id):
                handler.confirm_event(change_id)

        handler.commit_confirmations()
    """

    def get_events(self, key, types):
        """
        Fetch all new events of type key.

        :type key: str
        :param key:
            A change handler key to find unprocessed events for, *and* to use
            in later calls to :meth:`.commit_confirmations`.  See
            :func:`.validate_change_key` for valid change key values.

        :type types: list[_ChangeTypeCode]
        :param list types:
            Filter unprocessed change-log records by types.

            Use ``None`` to get all records, or provide a list of change types
            to include as a sequence of _ChangeTypeCode values.  This is the
            same parameter as ``types`` in :meth:`ChangeLog.get_log_events`.
        """
        key = validate_change_key(key)
        prev_ranges = list(get_ranges_for_key(self._db, key))

        events = []
        for min_id, max_id in _ranges_to_limits(prev_ranges):
            events.extend(
                self._db.get_log_events(min_id, max_id=max_id, types=types))

        # Setup for commit_confirmations()
        # TODO: This should ideally be re-written as a context manager
        self._current_key = key
        self._prev_ranges = prev_ranges
        self._sent_events = set(int(e['change_id']) for e in events)
        self._confirmed_events = set()

        return events

    def confirm_event(self, evt):
        """
        Confirm processing of an event.

        This should be called for every event that won't need re-processing
        the next time this change key is processed.
        """
        self._confirmed_events.add(int(evt['change_id']))

    def commit_confirmations(self):
        """
        Update database with confirmed events.

        Note that this method runs L{db.commit()}, which means that you can't
        run this if you try to dryrun functionality and wants to do a rollback
        afterwards. You could swap out L{db.commit} with L{db.rollback} or
        rather a dummy method that does nothing.

        TODO: Why does this commit, and break with rest of the API? There must
        be a reason for it. Can't remove it without checking all scripts!

        """

        # The idea here is to build the list of ranges each time.
        # Use this as an example:
        # [-]X--CC-C--[--]-C-C-C-X-X-C-X--[---]-X--X--C-C-C
        # Legend: [ and ]   existing range
        #         -         event not sent (i.e. not in self._sent_events)
        #         C         confirmed event
        #         X         unconfirmed event
        #
        # The first thing to do is to pretend [ and ] is C's:
        # C-CX--CC-C--C--C-C-C-C-X-X-C-X--C---C-X--X--C-C-C
        # The idea is to find sequences of X's, ignoring -, and make new
        # ranges excluding them:
        #
        # [-]X[-CC-C--C--C-C-C-C]X-X[C]X[-C---C]X--X[-C-C-]
        #
        # Note the details:
        # -1 is used as a number guaranteed to be smaller than every event id.
        # for every sequence of X's, find min(event_id) - 1
        # and max(event_id) + 1. This will be the new range.
        # If the largest event is confirmed, this should be equal to the upper
        # limit of the last range. (Else, an ending with -C-X-X will use
        # -C]X-X, i.e. let the last X's for next run.)

        # itertools.groupby iterates over sequences of X's or C's, making
        # isconf: True = C's, False = X's. The values is an iterator over the
        # change_id's in the current sequence returned. Our example is
        # returned: (each line one iteration in the outer for loop)
        # [-]
        #    X
        #       CC-C--[--]-C-C-C    (remember [ and ] are treated as C)
        #                        X-X
        #                            C
        #                              X
        #                                 [---]
        #                                       X--X
        #                                             C-C-C
        #
        # Note: if we did'nt insert [ and ] as C, the [---] on the seventh line
        # had been ignored. We need to keep this range, else the confirmed
        # events inside it will be returned at next run.
        #
        # Now, we take the X-lines, inserting ] at the start (values.next()-1),
        # and setting start = max(values)+1. If the X-line held a sole X, this
        # would generate a ValueError, so catch that. Start holds the id of the
        # start of the next range.
        #
        # If the first line is an X-line, we would insert a [-1, id-1], where
        # id-1 > -1, not doing any harm. If the first line is a C-line, it is
        # ignored, and we go to the second line, being the X-line. This should
        # be correct.
        prev = set(itertools.chain(*self._prev_ranges))
        ranges = []
        start = -1
        isconf = False  # to avoid NameError
        for isconf, values in itertools.groupby(
                sorted(self._sent_events | prev),
                (self._confirmed_events | prev).__contains__):
            if not isconf:
                end = next(values) - 1
                ranges.append((start, end))
                try:
                    start = max(values) + 1
                except Exception:
                    start = end + 2
        # If the last line is a C-line (might be the only line, too), we create
        # a range ending with the highest id returned.
        if isconf:
            ranges.append((
                start,
                max(itertools.chain(prev, self._confirmed_events)),
            ))

        if self._prev_ranges == ranges:
            return
        self._update_ranges(self._current_key, ranges)

    def _update_ranges(self, key, ranges):
        """Update DB with new ranges for a given handler key.

        Warning: This method does an actual `db.commit()`!

        All the previous ranges will be removed and replaced by the new, given
        `ranges`. Currently using the simple approach of deleting and
        re-inserting (maybe TODO: rewrite to use update for speed).

        :param str key: The given change handler key to update for
        :param list ranges:
            A list of the new ranges to be set. Each element in the list should
            be a two element list, where the first element represents the
            `first_id` and the second the `last_id`. Example:

                [(10, 110), (112, 201), (204, 415)]

        """
        # Clear all previous ranges
        clear_ranges_for_key(self._db, key)

        # Insert current ranges
        for first_id, last_id in ranges:
            add_range_for_key(self._db, key, first_id, last_id)

        self.commit()

    def _update_last_change_id(self, key, value):
        # TODO: Do we need this? Only used by a cerebrum-hacks script...
        self.execute(
            """
              UPDATE [:table schema=cerebrum name=change_handler_data]
              SET last_id=:value
              WHERE evthdlr_key=:key
            """,
            {
                'key': validate_change_key(key),
                'value': int(value),
            },
        )

    def list_handler_data(self):
        """Return all the registered change handler data.

        This is mostly for debugging. You should probably use `get_events(key)`
        instead of this method, for retrieving the events in a more suitable
        fashion.
        """
        # TODO: Do we need this?
        # Only used by contrib/change-handler-manipulate.py
        return get_all_ranges(self._db)
