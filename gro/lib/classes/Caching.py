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

import weakref
import time


class Caching(object):
    """ Handles caching of nodes.
    
    If a client asks for data which is already built from the database, a reference
    to the existing node instance will be returned.
    When no one is holding a reference to the node, it will be removed from the cache"""
    cache = weakref.WeakValueDictionary()

    def __new__(cls, *args, **vargs):
        """
        When a new node is requested, the system will check to see if it exists in the
        cache. If so, then a reference to it is returned. Otherwise a new node is created
        from data in the database and the reference to that is returned instead."""
        key = cls, cls.getKey(*args, **vargs)

        if key in cls.cache:
            return cls.cache[key]
        
        self = object.__new__(cls)
        self._key = key
        cls.cache[key] = self
        return self 

    def getPrimaryKey(self):
        """ Returns the primary key for the node. """
        return self._key

    def invalidateObject(cls, obj):
        """ Remove the node from the cache. """
        del cls.cache[obj]
    invalidateObject = classmethod(invalidateObject)

    def invalidate(self):
        """ Remove the node from the cache. """
        self.invalidateObject(self)

    def getKey(*args, **vargs): # this will make it a singleton
        pass
    getKey = staticmethod(getKey)
