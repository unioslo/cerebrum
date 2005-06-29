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

import threading
import weakref
import cereconf

from Cerebrum.extlib.sets import Set

from SpineExceptions import AlreadyLockedError, TransactionError
from Cerebrum.spine.server import LockHandler

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
        - If an object has a write lock on this object, no others get a read lock.
        - If an object has a read lock on this object, no others can get a write lock.
        - Many objects can have read locks on this object simultaneously.

    Objects that are to be locked should inherit this class.
    """

    def __init__(self, write_locker=None):
        """
        If a write locker is passed to this constructor, the object passed as
        the locker is given a write lock on the constructed object.
        """
        self.__read_locks = Set()
        self.__write_lock = None
        self.__locking_lock = threading.RLock()
        # If a locker (an object wanting to lock this object) was passed to us,
        # we lock ourselves for writing for that object.
        if write_locker is not None:
            self.lock_for_writing(write_locker)

    def lock_for_reading(self, locker):
        """
        Try to lock the object for reading.
        This method also checks if the client trying to get a read lock has
        other read locks that have timed out.
        """
        self.__locking_lock.acquire()
        if self.is_writelocked():
            self.__locking_lock.release()
            self.lock_for_writing(locker) # Update the timestamp for the write lock
        else:
            # Update the handler so that it knows this object is locked
            handler = LockHandler.get_handler()
            handler.add_lock(locker, self)
            # Add the read lock
            self.__read_locks.add(locker)
            self.__locking_lock.release()

    def lock_for_writing(self, locker):
        """
        Try to lock the object for writing.
        """
        # Check if someone else has a write lock
        self.__locking_lock.acquire()
        if self.is_writelocked() and self.get_writelock_holder() is not locker:
            self.__locking_lock.release()
            raise AlreadyLockedError, 'Write lock exists on %s' % self

        # Check if we and anyone else have a read lock. If others have read locks,
        # the object cannot be write locked.
        if locker in self.__read_locks:
            if len(self.__read_locks) > 1:
                self.__locking_lock.release()
                raise AlreadyLockedError, 'Other read locks exist on %s' % self
            self.__read_locks.remove(locker)
            assert len(self.__read_locks) == 0
        elif len(self.__read_locks) > 0:
            self.__locking_lock.release()
            raise AlreadyLockedError, 'Other read locks exist on %s' % self

        # Create a callback method so the object can be reset if the
        # lock holder is lost.
        def rollback(obj):
            if self.get_writelock_holder() is None:
                return
            self.reset()

        # Update the handler so that it knows this object is locked
        handler = LockHandler.get_handler()
        handler.add_lock(locker, self)

        # Create the write lock as a weak reference, resetting this object
        # if the client is lost (i.e. the transaction is ended abruptly)
        self.__write_lock = weakref.ref(locker, rollback)

        self.__locking_lock.release()
        
    def unlock(self, locker):
        """
        Remove all locks held by the given object.
        """
        assert not getattr(self, 'updated', None) # TODO: Is this right?
        
        self.__locking_lock.acquire()

        if self.has_writelock(locker):
            assert len(self.__read_locks) == 0 # There cannot be read locks when the object is write-locked
            self.__write_lock = None
        elif locker in self.__read_locks:
            self.__read_locks.remove(locker)

        handler = LockHandler.get_handler()
        handler.remove_lock(locker, self)
        self.__locking_lock.release()
        
    def has_readlock(self, locker):
        """
        Checks if the given object has a read lock on this object.
        """
        self.__locking_lock.acquire()
        has_lock = locker in self.__read_locks or self.has_writelock(locker)
        self.__locking_lock.release()
        return has_lock

    def has_writelock(self, locker):
        """
        Checks if the given object has a write lock on this object.
        """
        self.__locking_lock.acquire()
        has_lock = False
        if self.__write_lock is not None:
            if self.__write_lock() is locker:
                has_lock = True
        self.__locking_lock.release()
        return has_lock

    def get_readlock_holders(self):
        """
        Returns a (possibly empty) list of clients with a read lock on this item.
        """
        holders = []
        self.__locking_lock.acquire()
        for locker in self.__read_locks:
            holders.append(locker)
        self.__locking_lock.release()
        return holders
    
    def get_writelock_holder(self):
        """
        Returns a reference to the object holding a write lock on this object.
        Calling this method if a write lock is not present raises a
        TransactionError.
        """
        self.__locking_lock.acquire()
        if self.__write_lock is None:
            self.__locking_lock.release()
            raise TransactionError('No write lock on %s' % self)
        holder = self.__write_lock()
        self.__locking_lock.release()
        return holder

    def is_writelocked(self):
        """
        Checks if the object is write locked.
        """
        self.__locking_lock.acquire()
        locked = self.__write_lock is not None
        self.__locking_lock.release()
        return locked

# arch-tag: 47ac60c5-2e0e-42f8-b793-8202f48a23e3
