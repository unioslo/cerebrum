# -*- coding: iso-8859-1 -*-

# Copyright 2004 University of Oslo, Norway
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

import Database
from Cerebrum.gro.Cerebrum_core import Errors

from LockHolder import LockHolder

class Transaction(LockHolder):
    def __init__(self, client):
        LockHolder.__init__(self)
        self._refs = []
        self._db = Database.GroDatabase(client.get_id())
        self.transaction_started = True

    def add_ref(self, obj):
        """ Add a new object to this transaction.
        Changes made by this client will be written to the database
        if the transaction is commited and rolled back if the transaction
        is aborted."""

        if not self.transaction_started:
            raise Errors.TransactionError('No transaction started')

        self._refs.append(obj)

    def commit(self):
        """ Commits all changes made by this transaction to all objects
        changed.

        This transaction object cannot be used again."""

        if not self.transaction_started:
            raise Errors.TransactionError('No transaction started')

        try:
            self._db.commit()
            for item in self._refs:
                item.unlock(self)

        except Exception, e:
            raise Errors.TransactionError('Failed to commit: %s' % e)

        self._refs = None
        self.transaction_started = False
        

    def rollback(self):
        """ Discard all changes made to the objects in this transaction
        by the client in question.

        This transaction object cannot be used again."""

        if not self.transaction_started:
            raise Errors.TransactionError('No transaction started')

        self._db.rollback()

        for item in self._refs:
            if item.has_writelock(self):
                # FIXME: her burde vi kanskje skifte låsholder til den globale lås holderen...
                item.unlock(self)
                item.reset()
            else:
                item.unlock(self)

        self._db = None
        self._refs = None
        self.transaction_started = False

    def get_database(self):
        if self._db is None:
            raise Errors.TransactionError('No transaction started')
        else:
            return self._db

# arch-tag: a615bcdc-e962-4f74-a865-64ba66fffdfa
