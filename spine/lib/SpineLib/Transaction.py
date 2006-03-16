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

import Builder
import Database
from Cerebrum.extlib.sets import Set
# FIXME: We shouldn't have this dependency to server. 20060313 erikgors.
from Cerebrum.spine.server import LockHandler
from Locking import Locking, serialized_decorator
from SpineExceptions import TransactionError, NotFoundError
from DatabaseClass import DatabaseTransactionClass


__all__ = ['Transaction']

class Transaction(Builder.Builder):
    _ignore_Transaction = True
    
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

    get_encoding.signature = str

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
        self._lost_locks.append(object) 

        # We unlock the object here because there may be some time before the
        # transaction makes its next call and checks if it lost any locks
        if object.has_writelock(self):
            object.reset()
        object.unlock(self)
    lost_lock = serialized_decorator(lost_lock, '_lost_locks_lock')

    def check_lost_locks(self):
        """
        This method is called whenever the transaction tries to call a method
        on an object in Spine. If the transaction has lost a lock, it is rolled
        back, and an exception is raised.
        """
        if len(self._lost_locks):
            l = self._lost_locks.pop(0)
            self.rollback()
            raise TransactionError('Your lock on %s timed out, transaction was rolled back.' % l)
    check_lost_locks = serialized_decorator(check_lost_locks, '_lost_locks_lock')

    def __invalidate(self):
        handler = LockHandler.get_handler()
        handler.remove_transaction(self)
        self._refs = Set()
        self._session.remove_transaction(self)
        self._session = None
        self._db = None

    def _commit(self):
        """Commits all changes made by this transaction to all objects
        changed.

        This transaction object cannot be used again.
        """
        self._session.reset_timeout()

        try:
            self._db.commit()
            self._db.close()
            # FIXME: any reason why we use while and pop?
            while len(self._refs):
                item = self._refs.pop()
                if isinstance(item, Locking):
                    item.unlock(self)
        except Exception, e:
            self.rollback()
            raise TransactionError('Failed to commit: %s' % e)
        self.__invalidate()

    _commit = serialized_decorator(_commit, '_lost_locks_lock')
    def commit(self):
        return self._commit()
    commit.signature = None
        
    def _rollback(self):
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
                    item.reset()
                    if item.is_deleted():
                        item._undelete()
                item.unlock(self)
        self.__invalidate()

    _rollback = serialized_decorator(_rollback, '_lost_locks_lock')
    def rollback(self):
        return self._rollback()
    rollback.signature = None

    def get_database(self):
        if self._db is None:
            raise TransactionError('No transaction started')
        else:
            return self._db

    def build_methods(self):
        for cls in Builder.get_builder_classes():
            name = cls.__name__

            if cls.builder_ignore():
                continue

            method_name = 'get_' + convert_name(name)

            if hasattr(self, method_name):
                continue
            elif issubclass(cls, DatabaseTransactionClass):
                def blipp(cls):
                    def get_method(self, *args, **vargs):
                        obj = cls(self.get_database(), *args, **vargs)
                        if hasattr(obj, '_load_all_db'):
                            obj._load_all_db()
                        return obj
                    return get_method
                m = blipp(cls)
                args = []
                for i in cls.primary:
                    args.append((i.name, i.data_type))
            else:
                def blipp(cls):
                    def get_method(self, *args, **vargs):
                        return cls(*args, **vargs)
                    return get_method
                m = blipp(cls)
                args = []
                for i in cls.primary:
                    args.append((i.name, i.data_type))

            method = Builder.Method(method_name, cls, args, exceptions=[NotFoundError])
            Transaction.register_method(method, m)
        super(Transaction, cls).build_methods()
    build_methods = classmethod(build_methods)

def convert_name(name):
    name = list(name)
    name.reverse()
    last = name[0]
    new_name = name[0].lower()
    for i in name[1:]:
        if last.isupper() and i.islower():
            new_name += '_'
            new_name += i.lower()
            last = '_'
        elif last.islower() and i.isupper():
            new_name += i.lower()
            new_name += '_'
            last = '_'
        else:
            new_name += i.lower()
            last = i

    name = list(new_name)
    if name[-1] == '_':
        del name[-1]

    name.reverse()
    return ''.join(name)


# arch-tag: 79265054-583c-4ead-ae5b-3720b9d72810

# arch-tag: a0ea5825-7ab6-4444-a4f6-e3ecc7acae34
