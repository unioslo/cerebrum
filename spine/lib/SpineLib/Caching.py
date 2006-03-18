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

import time
import weakref

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

        Remember __init__ will be called, even when returning an old object
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
        self.__valid = True
        self.__deleted = False

        if cache is not None:
            self.cache[key] = self

        return self 

    def get_primary_key(self):
        """Returns the primary key for the object."""
        return self.__key[1]

    def get_minimum_lifetime(self):
        # FIXME: where should we put this default variable?
        return 10

    def invalidate(self):
        """ 
        Remove the node from the cache.
        Will not prevent this object from further use.
        """
        assert 0 # do not use. 20050706 erikgors.

        if self.cache is not None:
            assert self.__key in self.cache
            del self.cache[self.__key]

        self.__valid = False

    def is_valid(self):
        return self.__valid

    def _delete(self):
        self.__deleted = True

    def _undelete(self):
        self.__deleted = False

    def is_deleted(self):
        return self.__deleted

    def create_primary_key(*args, **vargs):
        return None # this will make it a singleton

    create_primary_key = staticmethod(create_primary_key)

# arch-tag: bc83a632-7f0c-4b97-8856-84a0b9cea0ac
