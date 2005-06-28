# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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

import cereconf
import threading
import time

_lock_handler = None

class LockHandler(threading.Thread):
    """
    The lock handler handles all object locks in Spine. All object that are to
    be locked tell the lock handler when they are accessed by their lock
    holders. The lock handler checks for timed out locks every
    SPINE_LOCK_CHECK_INTERVAL seconds, and removes any timed out locks.

    Objects that have a timed out read lock are not touched any further.  Write
    locked objects that have timed out are reset to their original state.
    """
    # TODO: Should we roll back the entire transaction when a write lock is timed out?
    def __init__(self):
        threading.Thread.__init__(self)
        self._transactions_lock = threading.RLock()
        self.running = False
        self._transactions = {}

    def add_transaction(self, transaction):
        self._transactions_lock.acquire()
        self._transactions[transaction] = {}
        self._transactions_lock.release()

    def remove_transaction(self, transaction):
        self._transactions_lock.acquire()
        assert self._transactions.has_key(transaction) # Transactions MUST be in this list
        del self._transactions[transaction]
        self._transactions_lock.release()

    def add_lock(self, transaction, object):
        """Updates the timestamp for the given transactions lock on the given object."""
        self._transactions_lock.acquire()
        assert self._transactions.has_key(transaction) # Transaction MUST be in this list
        self._transactions[transaction][object] = time.time() + cereconf.SPINE_LOCK_TIMEOUT
        self._transactions_lock.release()

    def remove_lock(self, transaction, object):
        self._transactions_lock.acquire()
        assert self._transactions.has_key(transaction)
        assert self._transactions[transaction].has_key(object)
        if self._transactions[transaction].has_key(object):
            del self._transactions[transaction][object]
        self._transactions_lock.release()

    def _get_timedout_locks(self):
        """Returns a list of the locks that have timed out."""
        deletable = []
        self._transactions_lock.acquire()
        now = time.time()
        for transaction in self._transactions:
            for object in self._transactions[transaction]:
                if self._transactions[transaction][object] <= now:
                    deletable.append((transaction, object))
        self._transactions_lock.release()
        return deletable

    def _check_times(self):
        deletable = self._get_timedout_locks()
        for transaction, object in deletable:
            transaction.lost_lock(object)

    def run(self):
        self.running = True
        while self.running:
            self._check_times()
            time.sleep(cereconf.SPINE_LOCK_CHECK_INTERVAL)

    def stop(self):
        self.running = False

def get_handler():
    """Returns the singleton instance of the lock handler."""
    global _lock_handler
    if _lock_handler is None:
        _lock_handler = LockHandler()
    return _lock_handler

# arch-tag: 6f392b10-e254-11d9-92c2-10a21545da7f
