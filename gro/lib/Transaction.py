from classes import Database
from Cerebrum_core import Errors

class Transaction:
    def begin(self):
        self._refs = []

    def addref(self, obj):
        """ Add a new object to this transaction.
        Changes made by this client will be written to the database
        if the transaction is commited and rolled back if the transaction
        is aborted."""

        if self._refs is None:
            raise Errors.TransactionError('No transaction started')

        self._refs.append(obj)

    def commit(self):
        """ Commits all changes made by this transaction to all objects
        changed.

        This transaction object cannot be used again."""

        db = Database.get_database()
        db.lock(self.entity.get_entity_id())
        
        try:
            for item in self._refs:
                if item.updated and item.is_writelocked_by_me(self):
                    item.save()
                item.unlock(self)

        except Exception, e:
            db.release()
            raise Errors.TransactionError('Failed to commit: %s' % e)

        db.release()
        self._refs = None
        

    def rollback(self):
        """ Discard all changes made to the objects in this transaction
        by the client in question.

        This transaction object cannot be used again."""
        for item in self._refs:
            if item.updated and item.is_writelocked_by_me(self):
                item.reload()
            item.unlock(self)

        self._refs = None
