import weakref
import time


class Caching(object):
    """ Handles caching of nodes.
    
    If a client asks for a node wich already exists, he will give him the node
    instead of creating a new node. When noone is holding a referance to the
    node, it will be removed from the cache."""
    cache = weakref.WeakValueDictionary()

    def __new__(cls, *args, **vargs):
        """
        When a new node is attempted to be created, it will be read
        from the database, or if it exists it will return the already
        existing node instead."""
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

