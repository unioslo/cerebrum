#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Database import Errors
from Cerebrum.Utils import Factory

class CLHandler(DatabaseAccessor):

    """CLHandler provides methods for update notifications when data
    is changed in Cerebrum using the ChangeLog.

    A key is used to keep track of which events was last reveived.
    The key -> change_id pointer will only be updated if commit() is
    called.

    TODO: This class takes care of any holes in the change_id
    sequence, asserting that no changes are lost.
    """

    def add_action_listener(remote_self, key, type=None):
        """Register remote_self as a call-back class implementing the
        method update_event(evt).  For use with a stand-alone
        ELInterface process that provides realtime synchronization."""
        # TODO: Implement this
        pass

    def get_events(self, key, types):
        """Fetch all new events of type.  

        types is a tuple of event-types to listen for."""
        ret = []
        last_id = self._get_last_change_id(key)
        max_id = last_id
        for evt in self._db.get_log_events(last_id+1, types=types):
            ret.append(evt)
            max_id = evt.change_id
        if max_id != last_id:
            self._update_last_change_id(key, max_id)
        return ret

    def _get_last_change_id(self, key):
        try:
            return self.query_1("""
            SELECT last_id
            FROM [:table schema=cerebrum name=change_handler_data]
            WHERE evthdlr_key=:key""", {'key': key})
        except Errors.NotFoundError:
           self.execute("""
           INSERT INTO [:table schema=cerebrum name=change_handler_data]
             (evthdlr_key, last_id)
           VALUES (:key, -1)""", {'key': key})
           return -1

    def _update_last_change_id(self, key, value):
        self.execute("""
        UPDATE [:table schema=cerebrum name=change_handler_data]
        SET last_id=:value
        WHERE evthdlr_key=:key""", {'key': key, 'value': value})
