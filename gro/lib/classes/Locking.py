#!/usr/bin/env python

import time
import weakref
import threading

from Cerebrum_core.Errors import AlreadyLockedError


""" Adds methods to lock down objects.

Will give objects the possibility to be locked for reading and writing
for a certain client, with a timeout with the help of the LockTimeout-class.
"""
class Locking( object ):

    def __init__( self ):
        # Weak dictionaries wich contains clientobjects and the time
        # they were locked. How are we gonna timeout the locking?
        self.readLocks = weakref.WeakKeyDictionary()
        self.writeLocks = weakref.WeakKeyDictionary()


    """ Prevent others from locking object.

    Several clients can put a readlock on the object, wich will prevent others
    from putting a writelock on this object.
    Raises an exception if someone else got a writelock on this object.
    """
    def readLock( self, client ):
        if not self.writeLocks:
            self.readLocks[ client ] = time.time()
        else:
            raise AlreadyLockedError( '''Someone already got writelock on
                this object''' )


    """ Obtain access to write to this object.

    Only one client can hold a writelock, and the client can only obtain a
    writelock if noone else already got a readlock.
    Raises an exception if someone else got readlock and/or writelock.
    """
    def writeLock( self, client ):
        if not self.writeLocks:
            if not self.readLocks:
                self.readLock( client )
            
            if len( self.readLocks ) == 1 and client in self.readLock:
                self.writeLocks[ client ] = time.time()
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
        if client in self.writeLocks:
            del self.writeLocks[ client ]
        if client in self.readLocks:
            del self.readLocks[ client ]


    """ Check if this object is locked for reading.
    
    Returns true if someone else than the client got a readlock.
    Returns false if noone has a readlock, or the client has a readlock.
    """
    def isReadLocked( self, client = None ):
        return not ( self.readLocks and client in self.readLocks )


    """ Check if this object is locked for writing.
    
    Returns true if the client dont got a writelock, and someone else got it.
    Returns false if noone has a writelock, or the client has a writelock.
    """
    def isWriteLocked( self, client = None ):
        return not ( self.writeLocks and client in self.writeLocks )
        #return ( not self.writeLocks or client not in self.writeLocks )
        #if not self.writeLocks or client in self.writeLocks:
        #    return False
        #else:
        #    return True



""" Handles timeout of locked entitys.

This class should have its own thread wich removes locks after a certain time.
Still not sure how it will work together with Locking.py
"""
class LockTimeout( threading.Thread ):

    def __init__( self ):
        threading.Thread.__init__( self )

