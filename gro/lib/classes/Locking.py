#!/usr/bin/env python

import time
import weakref
import threading

from Cerebrum.gro.Cerebrum_core import Errors
import Caching

__all__ = ['Locking', 'Locker']

""" Adds methods to lock down nodes.

Will give nodes the possibility to be locked for reading and writing
for a certain client, with a timeout with the help of the LockTimeout-class."""
class Locking( object ):

    def __init__( self ):
        # Weak dictionarie wich contains the clients and the time
        # they were locked. Time is used to timeout locks.
        self.readLocks = weakref.WeakKeyDictionary()
        self.writeLock = None


    """ Prevent others from locking nodes.

    Several clients can put a readlock on the node, wich will prevent others
    from putting a writelock on this node.
    Raises an exception if someone else got a writelock on this node, or
    if the client already got a readlock and/or writelock."""
    def lockForReading( self, client ):
        if not self.writeLock:
            if not self.isReadLockedByMe( client ):
                self.readLocks[ client ] = time.time()
            else:
                raise Errors.AlreadyLockedError( 'You already got a readlock on this node' )
        elif self.writeLock() is client:
            raise Errors.AlreadyLockedError( 'You already got a writelock on this node' )
        else:
            raise Errors.AlreadyLockedError( 'Someone already got writelock on this node' )


    """ Obtain access to write to this node.

    Only one client can hold a writelock, and the client can only obtain a
    writelock if he already got a readlock, and noone else got a readlock.
    Raises an exception if someone else got readlock and/or writelock, or
    if the client dont got a readlock yet."""
    def lockForWriting( self, client ):
        if not self.writeLock:
            if self.isReadLockedByMe( client ) and not self.isReadLockedByOther( client ):
                self.writeLock = weakref.ref( client, getattr( self, 'invalidateObject', None ) )
                self.writeLock = weakref.ref( client, test )
            elif not self.readLocks:
                raise Errors.NotLockedError( 'You dont got a readlock on this node yet' )
            else:
                raise Errors.AlreadyLockedError( 'Others got a readlock on this node,\
                    preventing you from getting a writelock' )
        elif self.writeLock() is client:
            raise Errors.AlreadyLockedError( 'You already got a writelock on this node' )
        else:
            raise Errors.AlreadyLockedError( 'Someone else already got a writelock on this node' )


    """ Remove your locks on this node.

    Will remove all your locks on this node if you got any. This is to prevent
    clients to lock the node after they are finished making changes.
    Raises an exception if the client dont got a lock on the node."""
    def unlock( self, client ):
        if self.isReadLockedByMe( client ):
            if self.isWriteLockedByMe( client ):
                # her må det sikkert gjøres noe opprydding i objectet..
                self.writeLock = None
            del self.readLocks[ client ]
        else:
            raise Errors.NotLockedError( 'You dont got any locks to unlock' )


    """ Check if this node is locked for reading by the client
    
    Returns true if the client got a readlock. Returns false if the client 
    dont got a readlock, regardless of who else got a readlock."""
    def isReadLockedByMe( self, client ):
        return ( client in self.readLocks.keys() )


    """ Check if this node is locked for reading by others than the client.
    
    Returns true if someone else than the client got a readlock.
    Returns false if noone has a readlock, or if the client is the only
    with a readlock."""
    def isReadLockedByOther( self, client ):
        return len(self.readLocks) > 1 or not self.readLocks and self.isReadLockedByMe()


    """ Check if this node is locked for writing by the client.
    
    Returns true if the client got a writelock.
    Returns false if noone has a writelock, or someone else got a writelock."""
    def isWriteLockedByMe( self, client ):
        return ( self.writeLock and client is self.writeLock() ) 


    """ Check if this node is locked for writing by someone else.

    Returns true if someone else than the client got a writelock on this node.
    Returns false if noone has a writelock, or the client has the writelock."""
    def isWriteLockedByOther( self, client ):
        return self.writeLock and ( client is not self.writeLock() )


    """ Returns a list over all who got a readlock.

    Returns a list with usernames for all who got a readlock on this node.
    Will return an informativ string if the node isnt readlocked."""
    def getReadLockers( self ):
        if self.readLocks:
            str = 'Users with readlock on this node:\n'
            for client in self.readLocks.keys():
                str += '%s\n' % client.getUsername()
        else:
            str = 'No readlock exists on this node'
        return str


    """ Returns the username wich got a writelock.

    Will return an informativ string if the node isnt writelocked."""
    def getWriteLocker( self ):
        if self.writeLock:
            str = '%s got a writelock on this node' % self.writeLock.getUsername()
        else:
            str = 'No writelock exists on this node'
        return str



""" Interface for clients.


Locker is the client wich locks down the node. If you want to lock down a node
you should extend this class, and implement the getUsername()-method."""
class Locker:

    def __init__( self, username ):
        self.username = username


    """ The name of the locking client.

    Should return a username wich identifies the person behind the client."""
    def getUsername():
        return ''



""" Handles timeout of locked nodes.

This class should have its own thread wich removes locks after a certain time.
Still not sure how it will work together with Locking"""
class LockTimeout( threading.Thread ):

    def __init__( self ):
        threading.Thread.__init__( self )

