from Cerebrum.gro import Cerebrum_core, Cerebrum_core__POA

class IteratorEmptyError( Cerebrum_core.Errors.IteratorEmptyError, StopIteration ):
    pass

class BulkIteratorImpl(Cerebrum_core__POA.BulkIterator):
    def __init__( self, values, amount = 2 ):
        self._values = values
        self._amount = amount

    def set_amount(self, amount):
        self._amount = amount
    def is_empty( self ):
        return not self._values and True or False

    def next( self ):
        if ( self.is_empty() ):
            raise IteratorEmptyError( 'is empty' )
        values = self._values[ :self._amount]
        self._values = self._values[ self._amount: ]
        return values

    def __iter__(self):
        return self

class BufferedIterator:
    def __init__( self, bulkIterator ):
        self._bi = bulkIterator
        self._buffer = []

    def is_empty( self ):
        return not (self._buffer or self._bi.is_empty()) and True or False

    def next( self ):
        if not self._buffer:
            try:
                self._buffer = self._bi.next()
            except Cerebrum_core.Errors.IteratorEmptyError:
                raise StopIteration

        return self._buffer.pop(0)

    def __iter__(self):
        return self


if __name__ == '__main__':
    l = []
    for i in BulkIteratorImpl([1,2,3,4]):
        l += i
    print l

    for i in BufferedIterator(BulkIteratorImpl([1,2,3,4])):
        print i,
    print
