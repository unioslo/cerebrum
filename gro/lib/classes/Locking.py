#!/usr/bin/env python

import time
import weakref
import threading

from Cerebrum.gro.Cerebrum_core.Error import AlreadyLockedError
import Caching


""" Adds methods to lock down objects.

Will give objects the possibility to be locked for reading and writing
for a certain client, with a timeout with the help of the LockTimeout-class.
"""
class Locking( object ):

    def __init__( self ):
        # Weak dictionarie wich contains the clients and the time
        # they were locked. Time is used to timeout locks.
        self.readLocks = weakref.WeakKeyDictionary()
        self.writeLock = None
        ref( self.writeLock, Caching.invalidate )


    """ Prevent others from locking object.

    Several clients can put a readlock on the object, wich will prevent others
    from putting a writelock on this object.
    Raises an exception if someone else got a writelock on this object.
    """
    def lockForReading( self, client ):
        if not self.writeLock:
            self.readLocks[ client ] = time.time()
        else:
            raise AlreadyLockedError( '''Someone already got writelock on
                this object''' )


    """ Obtain access to write to this object.

    Only one client can hold a writelock, and the client can only obtain a
    writelock if noone else already got a readlock.
    Raises an exception if someone else got readlock and/or writelock.
    """
    def lockForWriting( self, client ):
        if not self.writeLock:
            if not self.readLocks:
                self.lockForReading( self,  client )
            
            if len( self.readLocks ) == 1 and client in self.readLocks:
                self.writeLock = client
            else:
                raise AlreadyLockedError( '''Others got a readlock on this 
                    object, preventing you from getting a writelock''' )
        else:
            raise AlreadyLockedError( '''Someone else already got a
                writelock on this object''' )


    """ Remove your locks on this object.

    Will remove all your locks on this object if you got any. You cannot
    remove only a writelock, because <insert good reason here>...
    """
    def unlock( self, client ):
        if client is self.writeLock:
            self.writeLock = None
        if client in self.readLocks:
            del self.readLocks[ client ]


    """ Check if this object is locked for reading by the client
    
    Returns true if the client got a readlock.
    Returns false if the client dont got a readlock, regardless of who
    else got a readlock.
    """
    def isReadLockedByMe( self, client ):
        return ( client in self.readLocks )


    """ Check if this object is locked for reading by others than the client.
    
    Returns true if someone else than the client got a readlock.
    Returns false if noone has a readlock, or if the client is the only
    with a readlock.
    """
    def isReadLockedByOther:( self, client ):
        return len(readLocks) > 1 or ( client not in readLocks and readLocks )


    """ Check if this object is locked for writing by the client.
    
    Returns true if the client got a writelock.
    Returns false if noone has a writelock, or someone else got a writelock.
    """
    def isWriteLockedByMe( self, client ):
        return ( client is self.writeLock ) 


    """ Check if this object is locked for writing by someone else.

    Returns true if someone else than the client got a writelock on this node.
    Returns false if noone has a writelock, or the client has the writelock.
    """
    def isWriteLockedByOther( self, client ):
        return self.writeLock and ( client is not self.writeLock )



""" Handles timeout of locked nodes.

This class should have its own thread wich removes locks after a certain time.
Still not sure how it will work together with Locking
"""
class LockTimeout( threading.Thread ):

    def __init__( self ):
        threading.Thread.__init__( self )

