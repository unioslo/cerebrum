import weakref
import time

class Caching(object):
    cache = weakref.WeakValueDictionary()

    def __new__(cls, *args, **vargs):
        key = cls, cls.getKey(*args, **vargs)

        if key in cls.cache:
            return cls.cache[key]
        
        self = object.__new__(cls)
        self._key = key
        cls.cache[key] = self
        return self 

    def getPrimaryKey(self):
        return self._key

    def invalidateObject(cls, obj):
        del cls.cache[obj]
    invalidateObject = classmethod(invalidateObject)

    def invalidate(self):
        self.invalidateObject(self)
