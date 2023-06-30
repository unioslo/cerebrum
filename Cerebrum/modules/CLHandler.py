# -*- coding: utf-8 -*-
#
# Copyright 2003-2023 University of Oslo, Norway
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

This module adds a data model for fetching and and processing changes from the
changelog.  This is done by keeping a separate table that lists processed
change ids.
"""

import itertools
from Cerebrum.DatabaseAccessor import DatabaseAccessor


class CLHandler(DatabaseAccessor):

    """CLHandler provides methods for update notifications when data
    is changed in Cerebrum using the ChangeLog.

    A key is used to keep track of which events was last reveived.
    """

    def get_events(self, key, types):
        """Fetch all new events of type key.

        types is a tuple of event-types to listen for, or None.  The client
        should call confirm_event() for each event that it does not want
        to receive again, and commit_confirmations() once all events are
        processed."""

        prev_ranges = self._get_last_changes(key)
        if len(prev_ranges) == 0:
            prev_ranges = [[-1, -1]]
        self._prev_ranges = prev_ranges
        self._confirmed_events = set()
        self._sent_events = set()
        self._current_key = key
        ret = []
        for n in range(len(prev_ranges)):
            if n == len(prev_ranges)-1:
                min_id = prev_ranges[-1][1] + 1
                max_id = None
            else:
                min_id = prev_ranges[n][1] + 1
                max_id = prev_ranges[n+1][0] - 1
            for evt in self._db.get_log_events(min_id,
                                               max_id=max_id, types=types):
                ret.append(evt)
                self._sent_events.add(int(evt['change_id']))
        return ret

    def _get_last_changes(self, key):
        return [[int(r['first_id']), int(r['last_id'])]
                for r in self.query("""
        SELECT first_id, last_id
        FROM [:table schema=cerebrum name=change_handler_data]
        WHERE evthdlr_key=:key
        ORDER BY first_id""", {'key': key})]

    def confirm_event(self, evt):
        "Confirm that a given event was received OK."
        self._confirmed_events.add(int(evt['change_id']))

    def commit_confirmations(self):
        """Update database with confirmed events.

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
                end = values.next() - 1
                ranges.append([start, end])
                try:
                    start = max(values) + 1
                except Exception:
                    start = end + 2
        # If the last line is a C-line (might be the only line, too), we create
        # a range ending with the highest id returned.
        if isconf:
            ranges.append([start,
                           max(itertools.chain(prev, self._confirmed_events))])

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

                [[10, 110],
                 [112, 201],
                 [204, 415],
                 ]

        """
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=change_handler_data]
        WHERE evthdlr_key=:key""", {'key': key})

        for r in ranges:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=change_handler_data]
               (evthdlr_key, first_id, last_id)
               VALUES (:key, :first, :last)""", {
                'key': key, 'first': r[0], 'last': r[1]})
        self.commit()

    def _update_last_change_id(self, key, value):
        self.execute("""
        UPDATE [:table schema=cerebrum name=change_handler_data]
        SET last_id=:value
        WHERE evthdlr_key=:key""", {'key': key, 'value': value})

    def list_handler_data(self):
        """Return all the registered change handler data.

        This is mostly for debugging. You should probably use `get_events(key)`
        instead of this method, for retrieving the events in a more suitable
        fashion.

        """
        return self.query("""
            SELECT *
            FROM [:table schema=cerebrum name=change_handler_data]
            ORDER BY evthdlr_key""")
