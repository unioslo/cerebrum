#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

import weakref

import cereconf

from Cerebrum.gro import Transaction
from Cerebrum.gro.Cerebrum_core import Errors

import Caching, Scheduler


__all__ = ['Locking']

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

    def __init__(self):
        self.readLocks = weakref.WeakKeyDictionary()
        self.writeLock = None

    def lock_for_reading(self, client):
        """
        Try to lock the object for reading.
        """
        if self.writeLock:
            if self.writeLock() is client:
                return
            raise Errors.AlreadyLockedError, 'Write lock exists'
        if self.readLocks.has_key(client):
            return
        self.readLocks[client] = None

        def unlock(ref):
            o = ref()
            if o is not None and self.readLocks.has_key(o):
                self.reload()
                self.unlock(o)
                self._timed_out()
        scheduler = Scheduler.get_scheduler()
        scheduler.addTimer(cereconf.GRO_LOCK_TIMEOUT, unlock, weakref.ref(client))

    def lock_for_writing(self, client):
        """
        Try to lock the object for writing.
        """
        if self.writeLock and self.writeLock() is not client:
            raise Errors.AlreadyLockedError, 'Write lock exists'

        if self.readLocks.has_key(client):
            if len(self.readLocks) > 1:
                raise Errors.AlreadyLockedError, 'Other read locks exist'
            del self.readLocks[client]
        elif len(self.readLocks) > 0:
            raise Errors.AlreadyLockedError, 'Other read locks exist'

        def rollback(obj):
            self.reload()
        self.writeLock = weakref.ref(client, rollback)
        
        def unlock(ref):
            o = ref()
            if o is not None and self.has_writelock(o):
                self.reload()
                self.unlock(o)
                self._timed_out()
        scheduler = Scheduler.get_scheduler()
        scheduler.addTimer(cereconf.GRO_LOCK_TIMEOUT, unlock, weakref.ref(client))

    def _timed_out(self):
        """
        Raise a TransactionError telling that the lock has timed out.
        """
        raise Errors.TransactionError('Your lock has timed out')

    def unlock(self, client):
        """
        Remove all locks held by the given client.
        """
        assert not getattr(self, 'updated', None)
        
        if self.has_writelock(client):
            self.writeLock = None
        elif self.readLocks.has_key(client):
            del self.readLocks[client]

    def has_writelock(self, locker):
        """
        Checks if the given client has a write lock.
        """
        return self.writeLock and self.writeLock() is locker

    def get_readlockers(self):
        """
        Returns a list of clients with a read lock on this item.
        """
        users = []
        for client in self.readLocks.keys():
            users.append(client)
        return users

    def get_writelockers(self):
        """
        Returns the client with a write lock or None.
        """
        if self.writeLock:
            obj = self.writeLock()
            return obj
        return None
