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
import traceback

import Database
from Cerebrum.extlib.sets import Set
from Cerebrum.spine.server import LockHandler
from Locking import Locking
from SpineExceptions import TransactionError


__all__ = ['Transaction']

class Transaction:
    def __init__(self, session):
        handler = LockHandler.get_handler()
        handler.add_transaction(self)
        self._lost_locks = []
        self._lost_locks_lock = threading.RLock()
        self._refs = Set()
        self._session = session
        self._session.reset_timeout()
        self._db = Database.SpineDatabase(session.client.get_id())

    def get_encoding(self):
        return self._session.get_encoding()

    def add_ref(self, obj):
        """Add a new object to this transaction.

        Changes made on the object by this transaction will be written to the
        database if the transaction is commited and rolled back if the
        transaction is aborted.
        """
        self._session.reset_timeout()
        self._refs.add(obj)

    def lost_lock(self, object):
        """
        This method is called by the lock handler when the transaction
        has lost a lock on the given object.

        The method checks if the lost lock is a write lock. If that is the
        case, the object is reset to its original state.
        """
        assert isinstance(object, Locking) # This method should only be called with a lockable object
        assert object in self._refs # The object must be referenced by this transaction
        self._refs.remove(object)
        self._lost_locks_lock.acquire()
        self._lost_locks.append(object) 
        self._lost_locks_lock.release()
        # We unlock the object here because there may be some time before the
        # transaction makes its next call and checks if it lost any locks
        if object.has_writelock(self):
            object.reset()
        object.unlock(self)

    def check_lost_locks(self):
        """
        This method is called whenever the transaction tries to call a method
        on an object in Spine. If the transaction has lost a lock, it is rolled
        back, and an exception is raised.
        """
        self._lost_locks_lock.acquire()
        if len(self._lost_locks):
            l = self._lost_locks.pop(0)
            self.rollback()
            self._lost_locks_lock.release()
            raise TransactionError('Your lock on %s timed out, transaction was rolled back.' % l)

    def _invalidate(self):
        handler = LockHandler.get_handler()
        handler.remove_transaction(self)
        self._refs = None
        self._session.remove_transaction(self)
        self._session = None
        self._db = None

    def commit(self):
        """Commits all changes made by this transaction to all objects
        changed.

        This transaction object cannot be used again.
        """
        self._session.reset_timeout()

        try:
            self._db.commit()
            self._db.close()
            while len(self._refs):
                item = self._refs.pop()
                if isinstance(item, Locking):
                    item.unlock(self)
        except Exception, e:
            self.rollback()
            raise TransactionError('Failed to commit: %s' % e)
        self._invalidate()
        

    def rollback(self):
        """Discard all changes made to the objects in this transaction
        by the client in question.

        This transaction object cannot be used again.
        """
        assert self._db is not None # Rollback should only be called ONCE on a transaction
        try:
            self._db.rollback()
            self._db.close()
        except:
            print 'DEBUG: Unable to rollback the database object!'
            traceback.print_exc() # TODO: Log this

        while len(self._refs):
            item = self._refs.pop()
            if isinstance(item, Locking):
                if item.has_writelock(self):
                    item.invalidate()
                item.unlock(self)
        self._invalidate()

    def get_database(self):
        if self._db is None:
            raise TransactionError('No transaction started')
        else:
            return self._db

# arch-tag: a0ea5825-7ab6-4444-a4f6-e3ecc7acae34
