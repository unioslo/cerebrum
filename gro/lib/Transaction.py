from classes import Database
from Cerebrum_core import Errors

from classes.LockHolder import LockHolder

class Transaction(LockHolder):
    def __init__(self, client):
        LockHolder.__init__(self)
        self.client = client
        self._refs = None
        self._db = None
        self.transaction_started = False

    def begin(self):
        if self.transaction_started:
            raise Errors.TransactionError('Transaction has already started')
        else:
            self._refs = []
            self._db = Database.GroDatabase(self.client.get_entity_id())
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
