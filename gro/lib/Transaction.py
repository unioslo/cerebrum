class Transaction:

    def __init__( self, client ):
        """ Creates a new transaction.
        client specifies the APHandler object used for the transaction.
        """
        self.client = client
        self._refs = []

    def addref( self, obj ):
        """ Add a new object to this transaction.
        Changes made by this client will be written to the database
        if the transaction is commited and rolled back if the transaction
        is aborted."""

        if self._refs is None:
            #TODO: Throw an exception
            pass
        
        self._refs += [obj]

    def commit( self ):
        """ Commits all changes made by this transaction to all objects
        changed.

        This transaction object cannot be used again."""

        for item in self._refs:
            if item.updated and item.isWriteLockedByMe():
                #TODO: Do the actual writing
                pass
            else:
                pass
                                                
        for item in self._refs:
            item.unlock( client )

        item.refs = None
        
    def rollback( self ):
        """ Discard all changes made to the objects in this transaction
        by the client in question.

        This transaction object cannot be used again."""
        for item in self._refs:
            item.rollback()

        for item in self._refs:
            item.unlock()

        item.refs = None
