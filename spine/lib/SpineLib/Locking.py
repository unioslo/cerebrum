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

import time, weakref
import cereconf

from SpineExceptions import SpineException
from Transaction import Transaction, TransactionError
import Scheduler

__all__ = ['Locking', 'AlreadyLockedError']

class AlreadyLockedError(SpineException):
    pass

class Locking(object):
    """
    Implements support for locking an object.
     Existing |  read(self)  | read(others) | write(self) | write(others)
    Requested |              |              |             |
    ----------+--------------+--------------+-------------+---------------
      read    |      N/A     |       Y      |   N/A       |       N
      write   |      Y       |       N      |   N/A       |       N

    In other words:
        - A write lock implies a read lock.
        - If a client has a write lock, no others have a read lock.
        - If a client has a read lock, no others can get a write lock.
        - Many clients can have read locks simultaneously.
    """

    def __init__(self, write_lock=None):
        self.read_locks = weakref.WeakKeyDictionary()
        self.write_lock = None
        if write_lock is not None:
            self.lock_for_writing(write_lock)

    def lock_for_reading(self, client):
        """
        Try to lock the object for reading.
        """
        self.__has_timeouts(client)

        if self.write_lock:
            ref, locktime = self.write_lock
            if ref() is client:
                self.lock_for_writing(client)
                return
            raise AlreadyLockedError, 'Write lock exists on %s' % self
        self.read_locks[client] = time.time()

        def unlock(ref):
            o = ref()
            if o is not None and self.read_locks.has_key(o):
                locktime = self.read_locks[o]
                if locktime + cereconf.SPINE_LOCK_TIMEOUT > time.time():
                    return
                self.reset()
                self.unlock(o)
                self.__lost_lock(o)

#        scheduler = Scheduler.get_scheduler()
#        scheduler.addTimer(cereconf.SPINE_LOCK_TIMEOUT, unlock, weakref.ref(client))

    def __lost_lock(self, client):
        client.lost_locks.append(self)

    def __has_timeouts(self, client):
        if len(client.lost_locks) > 0:
            l = client.lost_locks.pop(0)
            raise TransactionError('Your lock on %s timed out' % l)

    def lock_for_writing(self, client):
        """
        Try to lock the object for writing.
        """
        self.__has_timeouts(client)

        if self.is_writelocked() and self.get_writelock_holder() is not client:
            raise AlreadyLockedError, 'Write lock exists on %s' % self

        if self.read_locks.has_key(client):
            if len(self.read_locks) > 1:
                raise AlreadyLockedError, 'Other read locks exist on %s' % self
            del self.read_locks[client]
        elif len(self.read_locks) > 0:
            raise AlreadyLockedError, 'Other read locks exist on %s' % self

        def rollback(obj):
            self.reset()

        self.write_lock = weakref.ref(client, rollback), time.time()
        
        def unlock(ref):
            o = ref()
            if o is not None and self.has_writelock(o):
                ref, locktime = self.write_lock
                if locktime + cereconf.SPINE_LOCK_TIMEOUT > time.time():
                    return
                self.reset()
                self.unlock(o)
                self.__lost_lock(o)
                    
#        scheduler = Scheduler.get_scheduler()
#        scheduler.addTimer(cereconf.SPINE_LOCK_TIMEOUT, unlock, weakref.ref(client))

    def unlock(self, client):
        """
        Remove all locks held by the given client.
        """
        assert not getattr(self, 'updated', None)
        
        if self.has_writelock(client):
            self.write_lock = None
        elif self.read_locks.has_key(client):
            del self.read_locks[client]
        
    def has_readlock(self, locker):
        """
        Checks if the given client has a read lock.
        """
        return self.read_locks.has_key(locker) or self.has_writelock(locker)

    def has_writelock(self, locker):
        """
        Checks if the given client has a write lock.
        """
        if self.write_lock is None:
            return False
        ref, locktime = self.write_lock
        return ref() is locker

    def get_readlock_holders(self):
        """
        Returns a (possibly empty) list of clients with a read lock on this item.
        """
        holders = []
        for client in self.read_locks.keys():
            holders.append(client)
        return holders
    
    def get_writelock_holder(self):
        if self.write_lock is None:
            raise Exception('No write lock on %s' % self)
        ref, locktime = self.write_lock
        return ref()

    def is_writelocked(self):
        return self.write_lock is not None


# arch-tag: 47ac60c5-2e0e-42f8-b793-8202f48a23e3
