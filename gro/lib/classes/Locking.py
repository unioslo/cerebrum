#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

import time
import weakref
import threading

from Cerebrum.gro.Cerebrum_core import Errors
import Caching

__all__ = ['Locking', 'Locker']

class Locking( object ):
    """Adds methods to lock down nodes.

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
    - You will not get a lock if someone else got a write lock
    - You will not get a write lock if someone else got a lock
    """

    def __init__( self ):
        # Weak dictionary which contains the clients and the time
        # they were locked. Time is used to timeout locks.
        self.readLocks = weakref.WeakKeyDictionary()
        self.writeLock = None

    def lock_for_reading( self, client ):
        """Request a readlock on this node.

        If the node is already writelocked an exception is raised.
        """
        if self.is_writelocked_by_other( client ):
            raise Errors.AlreadyLockedError, 'Node is writelocked by someone else.'
        self.readLocks[ client ] = time.time()

    def lock_for_writing( self, client ):
        """Request a writelock on this node.

        If the node is already writelocked an exception is raised.
        If someone else also got a readlock on the node, an exception is raised.
        """
        if self.is_writelocked_by_other( client ):
            raise Errors.AlreadyLockedError, 'A writelock already exists on this node'

        if self.is_readlocked_by_other( client ):
            raise Errors.AlreadyLockedError( 'Others got a readlock on this node,' \
                'preventing you from getting a writelock' )

        if not self.is_readlocked_by_me( client ):
            self.lock_for_reading( client )

        def rollback(obj):
            self.reload()
        self.writeLock = weakref.ref( client, rollback )

    def unlock( self, client ):
        """Remove all locks held by client on this node.
        """
        assert not getattr(self, 'updated', None) # trying to unlock a changed object

        if self.is_readlocked_by_me( client ):
            if self.is_writelocked_by_me( client ):
                self.writeLock = None
            del self.readLocks[ client ]

    def is_readlocked_by_me( self, client ):
        """Check if this node is locked for reading by the client
    
        Returns true if the client got a readlock and false otherwise.
        Other locks are disregarded.
        """
        return ( client in self.readLocks.keys() )

    def is_readlocked_by_other( self, client ):
        """Check if this node is locked for reading by other clients.
    
        Returns true if a client different to the specified client got a readlock
        and false otherwise.
        """
        return len( self.readLocks ) > 1 or (
               self.readLocks and not self.is_readlocked_by_me( client ) )

    def is_writelocked_by_me( self, client ):
        """Check if this node is locked for writing by the client.
    
        Returns true if the client specified got a write lock and false otherwise.
        """
        return ( self.writeLock and client is self.writeLock() ) 

    def is_writelocked_by_other( self, client ):
        """Check if this node is locked for writing by another client.

        Returns true if a client different to the client specified got a writelock
        and false otherwise.
        """
        return self.writeLock and ( client is not self.writeLock() )

    def get_readlockers( self ):
        """Returns a list over all who got a readlock.

        Returns a list with usernames for all who got a readlock on this node.
        Will return an informative string if the node isn't locked for reading.
        """
        if self.readLocks:
            str = 'Users with readlock on this node:\n'
            for client in self.readLocks.keys():
                str += '%s\n' % client.get_username()
        else:
            str = 'No readlock exists on this node'
        return str

    def get_writelocker( self ):
        """Returns the username wich got a writelock.

        Will return an informative string if the node isn't locked for writing.
        """
        if self.writeLock:
            str = '%s got a write lock on this node' % self.writeLock().get_username()
        else:
            str = 'No write lock exists on this node'
        return str



class Locker:
    """Interface for clients.

    Locker is the client which locks the node. If you want to lock a node
    you should extend this class, and implement the getUsername() method.
    """

    def __init__( self, username ):
        self.username = username

    def get_username(self):
        """The name of the locking client.

        Should return a username wich identifies the person behind the client.
        """
        return self.username



class LockTimeout( threading.Thread ):
    """Handles timeout of locked nodes.

    This class should have it's own thread which removes locks after a certain time.
    Still not sure how it will work together with Locking.
    """

    def __init__( self ):
        threading.Thread.__init__( self )

