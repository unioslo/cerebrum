#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Database import Errors
from Cerebrum.Utils import Factory

class CLHandler(DatabaseAccessor):

    """CLHandler provides methods for update notifications when data
    is changed in Cerebrum using the ChangeLog.

    A key is used to keep track of which events was last reveived.
    """

    def add_action_listener(remote_self, key, type=None):
        """Register remote_self as a call-back class implementing the
        method update_event(evt).  For use with a stand-alone
        ELInterface process that provides realtime synchronization."""
        # TODO: Implement this
        pass

    def get_events(self, key, types):
        """Fetch all new events of type.

        types is a tuple of event-types to listen for.  The client
        should call confirm_event() for each event that it does not want
        to receive again, and commit_confirmations() once all events are
        processed."""

        prev_ranges = self._get_last_changes(key)
        if len(prev_ranges) == 0:
            prev_ranges = [[-1, -1]]
        self._prev_ranges = prev_ranges
        self._confirmed_events = []
        self._sent_events = []
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
                self._sent_events.append(int(evt['change_id']))
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
        self._confirmed_events.append(int(evt['change_id']))

    def commit_confirmations(self):
        """Update database with information about what events a have
        been received OK"""
        debug = False
        self._confirmed_events.sort()
        new_ranges = self._prev_ranges[:]
        range_no = 0
        i_sent = i_confirmed = 0
        updated = False
        if len(self._confirmed_events) == 0:
            return  # No update needed
        # We know what events we sent to the client, which events the
        # client confirmed this time, as well as what ranges of events the
        # client has previously acknowledged.  Now we iterate over all
        # sent events and determine which range the event corresponds to.
        # 
        # Since we know that the _sent_events list does not contain holes,
        # we can update the range with the new end-value if the client
        # confirmed the event.  If the client did not confirm the event,
        # we must create a new range to fit the next confirmed event.
        found_hole = False
        while i_sent < len(self._sent_events):
            tmp_evt_id = self._sent_events[i_sent]
            # Find a range corresponding to this event
            while (range_no+1 < len(new_ranges) and
                   tmp_evt_id >= new_ranges[range_no+1][0]):
                range_no += 1
            if debug:
                print "Matching range# %i for %i (len=%i) hole=%s" % (
                    range_no, tmp_evt_id, len(new_ranges), found_hole)
            # Check if the event was confirmed
            while (i_confirmed+1 < len(self._confirmed_events) and
                   self._confirmed_events[i_confirmed] < tmp_evt_id):
                i_confirmed += 1
            if (self._confirmed_events[i_confirmed] == tmp_evt_id):
                # The event was confirmed, uppdate corresponding range
                if debug:
                    print "  C: hole=%i (%s)" % (found_hole, new_ranges)

                if (tmp_evt_id > new_ranges[range_no][1] and
                    tmp_evt_id > new_ranges[range_no][0]):
                    updated = True
                    if found_hole:
                        if range_no < len(new_ranges):
                            new_ranges.insert(range_no+1, [tmp_evt_id, tmp_evt_id])
                        else:
                            new_ranges.append([tmp_evt_id, tmp_evt_id])
                        found_hole = False
                    else:
                        new_ranges[range_no][1] = tmp_evt_id
                if debug:
                    print "  RES: %s" % new_ranges
            else:
                found_hole = True
            i_sent += 1
        if debug:
            print "NR: %s (%s)" % (new_ranges, updated)

        # TODO:
        #
        # Now, loop through all notified events, and if two consecutive
        # events matches the last and first element in two ranges, join
        # them.  Also join if the event is older than N seconds

        if not updated:
            return
        # Update DB, currently using the simple approach of deleting and
        # re-inserting (maybe TODO: rewrite to use update for speed)
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=change_handler_data]
        WHERE evthdlr_key=:key""", {'key': self._current_key})

        for r in new_ranges:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=change_handler_data]
               (evthdlr_key, first_id, last_id)
               VALUES (:key, :first, :last)""", {
                'key': self._current_key, 'first': r[0], 'last': r[1]})
        self.commit()


    def _update_last_change_id(self, key, value):
        self.execute("""
        UPDATE [:table schema=cerebrum name=change_handler_data]
        SET last_id=:value
        WHERE evthdlr_key=:key""", {'key': key, 'value': value})
