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

import Scheduler

class Caching(object):
    """ Handles caching of objects.
    
    If a new object is requested which is already created, a reference to the existing
    object will be returned. The object is automatically removed from the cache when no one
    is no longer holding a reference to it"""

    cache = weakref.WeakValueDictionary()

    def __new__(cls, *args, **vargs):
        """
        When a new object is requested, the system will check, using
        cls.create_primary_key(*args, **vargs) to see if it exists in the cache. If so, then
        a reference to it is returned. Otherwise a new object is created and the reference to
        that is returned instead."""

        # FIXME: vi trenger låsing her

        # getting the key to uniquely identify this object
        primary_key = cls.create_primary_key(*args, **vargs)
        key = cls, primary_key # cls is inserted to avoid collisions

        # if it allready exists, return the old one
        if key in cls.cache:
            return cls.cache[key]
        
        # create a new object
        self = object.__new__(cls)

        cls.cache_object(self, primary_key)

        # remember __init__ will be run, even though it is an old object
        return self 

    def get_primary_key(self):
        """ Returns the primary key for the object. """
        return self._key[1]

    def invalidate_object(cls, obj):
        """ Remove the node from the cache. """
        assert 0 # uh. this is not the right way to do this.
        del cls.cache[obj._key]

    invalidate_object = classmethod(invalidate_object)

    def get_minimum_lifetime(self):
        # FIXME: where should we put this default variable?
        return 10

    def cache_object(cls, obj, primary_key):
        key = cls, primary_key

        obj._key = key
        cls.cache[key] = obj

        minimum_lifetime = obj.get_minimum_lifetime()

        if minimum_lifetime:
            def holder(): # this will make sure a reference to obj exists as long as holder exists
                obj

            scheduler = Scheduler.get_scheduler()
            scheduler.addTimer(obj.get_minimum_lifetime(), holder)

    cache_object = classmethod(cache_object)

    def invalidate(self):
        """ Remove the node from the cache. """
        self.invalidate_object(self)

    def cache_self(self):
        self.cache_object(self, self.get_primary_key())

    def create_primary_key(*args, **vargs):
        return None # this will make it a singleton

    create_primary_key = staticmethod(create_primary_key)
