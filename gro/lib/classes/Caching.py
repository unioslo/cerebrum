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
