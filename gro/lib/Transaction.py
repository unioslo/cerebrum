from classes import Database
from Cerebrum_core import Errors

class Transaction:
    def __init__(self, client):
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
            for item in self._refs:
                if item.updated and item.has_writelock(self):
                    item.save()
                item.unlock(self)

        except Exception, e:
            db.release()
            raise Errors.TransactionError('Failed to commit: %s' % e)

        self._db.commit()
        self._refs = None
        self.transaction_started = False
        

    def rollback(self):
        """ Discard all changes made to the objects in this transaction
        by the client in question.

        This transaction object cannot be used again."""

        if not self.transaction_started:
            raise Errors.TransactionError('No transaction started')

        for item in self._refs:
            if item.updated and item.has_writelock(self):
                item.reload()
            item.unlock(self)

        self._db.rollback()
        self._db = None
        self._refs = None
        self.transaction_started = False

    def get_database(self):
        if self._db is None:
            raise Errors.TransactionError('No transaction started')
        else:
            return self._db
