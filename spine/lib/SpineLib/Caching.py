# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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

import Scheduler

class Caching(object):
    """Handles caching of objects.
    
    If a new object is requested which is already created, a
    reference to the existing object will be returned.
    The object is automatically removed from the cache when no
    one is no longer holding a reference to it.
    """

    global_cache = weakref.WeakValueDictionary()

    def __new__(cls, *args, **vargs):
        """
        When a new object is requested, the system will check, using
        cls.create_primary_key(*args, **vargs) to see if it exists in
        the cache. If so, then a reference to it is returned.
        Otherwise a new object is created and the reference to that is
        returned instead.
        """
        # FIXME: vi trenger låsing her
        cache = vargs.get('cache', cls.global_cache)
        if 'cache' in vargs:
            del vargs['cache']

        # getting the key to uniquely identify this object
        primary_key = cls.create_primary_key(*args, **vargs)
        assert type(primary_key) == tuple
        key = cls, primary_key # cls is inserted to avoid collisions

        # if it allready exists, return the old one
        if cache is not None and key in cache:
            return cache[key]
        
        # create a new object
        self = object.__new__(cls)
        self.__key = key
        self.cache = cache

        if cache is not None:
            self.cache_self()

        # remember __init__ will be run, even though it is an old object
        return self 

    def __init__(self):
        mark = '_%s%s' % (self.__class__.__name__, id(self))
        if hasattr(self, mark):
            return getattr(self, mark)
        setattr(self, mark, time.time())

    def get_primary_key(self):
        """Returns the primary key for the object."""
        return self.__key[1]

    def get_minimum_lifetime(self):
        # FIXME: where should we put this default variable?
        return 10

    def cache_self(self):
        key = self.__class__, self.get_primary_key()

        self.cache[key] = self

        minimum_lifetime = self.get_minimum_lifetime()

        if minimum_lifetime:
            def holder(): # this will make sure a reference to self exists as long as holder exists
                self

#            scheduler = Scheduler.get_scheduler()
#            scheduler.addTimer(minimum_lifetime, holder)

    def invalidate(self):
        """ Remove the node from the cache.
        
        Will not prevent this object from futher use.
        """
        if self.cache is not None:
            del self.cache[self.__key]

    def create_primary_key(*args, **vargs):
        return None # this will make it a singleton

    create_primary_key = staticmethod(create_primary_key)

# arch-tag: bc83a632-7f0c-4b97-8856-84a0b9cea0ac
