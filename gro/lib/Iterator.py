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

# arch-tag: 069179c8-c053-45ae-a502-410517a9dca1
