#!/usr/bin/env python

import time
import weakref
import threading

from Cerebrum.gro.Cerebrum_core import Errors
import Caching

__all__ = ['Locking', 'Locker']

class Locking( object ):
    """ Adds methods to lock down nodes.

    Will give nodes the possibility to be locked for reading and writing
    for a certain client, with a timeout with the help of the LockTimeout-class.
    Locks will be granted according to the following matrix:

    Existing  |  Read(self)  | Read(others) | Write(self) | Write(others)
    Requested |              |              |             |
    ----------+--------------+--------------+-------------+---------------
      Read    |      N/A     |       Y      |   N/A       |       N
      Write   |      Y       |       N      |   N/A       |       N

    In other words:
    - You need a read lock to obtain a write lock
    - Obtaining a lock you already got will lead to an exception
    - You will not get a lock if someone else got a write lock
    - You will not get a write lock if someone else got a lock
      """

    def __init__( self ):
        # Weak dictionary which contains the clients and the time
        # they were locked. Time is used to timeout locks.
        self.readLocks = weakref.WeakKeyDictionary()
        self.writeLock = None

    def lockForReading( self, client ):
        """Request a read lock on this node."""

        if not self.writeLock:
            if not self.isReadLockedByMe( client ):
                self.readLocks[ client ] = time.time()
            else:
                raise Errors.AlreadyLockedError( 'You already got a readlock on this node' )
        elif self.writeLock() is client:
            raise Errors.AlreadyLockedError( 'You already got a writelock on this node' )
        else:
            raise Errors.AlreadyLockedError( 'Someone already got writelock on this node' )

    def lockForWriting( self, client ):
        """Request a write lock on this node."""
        if not self.writeLock:
            if self.isReadLockedByMe( client ) and not self.isReadLockedByOther( client ):
                def rollback(obj):
                    self.rollback()
                self.writeLock = weakref.ref( client, rollback )
            elif not self.readLocks:
                raise Errors.NotLockedError( 'You dont got a readlock on this node' )
            else:
                raise Errors.AlreadyLockedError( 'Others got a readlock on this node,\
                    preventing you from getting a writelock' )
        elif self.writeLock() is client:
            raise Errors.AlreadyLockedError( 'You already got a writelock on this node' )
        else:
            raise Errors.AlreadyLockedError( 'A writelock already exists on this node' )

    def unlock( self, client ):
        """Remove all locks held by client on this node.
        Raises an exception if the client doesn't have a lock on this node."""
        if self.isReadLockedByMe( client ):
            if self.isWriteLockedByMe( client ):
                # her må det sikkert gjøres noe opprydding i objectet..
                self.writeLock = None
            del self.readLocks[ client ]
        else:
            raise Errors.NotLockedError( 'You dont got any locks to unlock' )

    def isReadLockedByMe( self, client ):
        """ Check if this node is locked for reading by the client
    
        Returns true if the client got a read lock and false otherwise.
        Other locks are disregarded."""
        return ( client in self.readLocks.keys() )

    def isReadLockedByOther( self, client ):
        """ Check if this node is locked for reading by other clients.
    
        Returns true if a client different to the specified client got a read lock
        and false otherwise."""
        return len(self.readLocks) > 1 or not self.readLocks and self.isReadLockedByMe()

    def isWriteLockedByMe( self, client ):
        """ Check if this node is locked for writing by the client.
    
        Returns true if the client specified got a write lock and false otherwise."""
        return ( self.writeLock and client is self.writeLock() ) 

    def isWriteLockedByOther( self, client ):
        """ Check if this node is locked for writing by another client.

        Returns true if a client different to the client specified got a write lock
        and false otherwise."""
        return self.writeLock and ( client is not self.writeLock() )

    def getReadLockers( self ):
        """ Returns a list over all who got a readlock.

        Returns a list with usernames for all who got a readlock on this node.
        Will return an informative string if the node isn't locked for reading."""
        if self.readLocks:
            str = 'Users with readlock on this node:\n'
            for client in self.readLocks.keys():
                str += '%s\n' % client.getUsername()
        else:
            str = 'No readlock exists on this node'
        return str

    def getWriteLocker( self ):
        """ Returns the username wich got a writelock.

        Will return an informative string if the node isn't locked for writing."""
        if self.writeLock:
            str = '%s got a write lock on this node' % self.writeLock.getUsername()
        else:
            str = 'No write lock exists on this node'
        return str



class Locker:
    """ Interface for clients.

    Locker is the client which locks the node. If you want to lock a node
    you should extend this class, and implement the getUsername() method."""

    def __init__( self, username ):
        self.username = username

    def getUsername():
        """ The name of the locking client.

        Should return a username wich identifies the person behind the client."""
        return ''



class LockTimeout( threading.Thread ):
    """ Handles timeout of locked nodes.

    This class should have it's own thread which removes locks after a certain time.
    Still not sure how it will work together with Locking"""

    def __init__( self ):
        threading.Thread.__init__( self )

