import weakref
import time

class Caching(object):
    cache = weakref.WeakValueDictionary()

    def __new__(cls, *args, **vargs):
        key = cls, cls.getKey(*args, **vargs)

        if key in cls.cache:
            return cls.cache[key]
        
        self = object.__new__(cls)
        cls.cache[key] = self
        return self 

    def invalidateObject(cls, obj):
        del cls.cache[obj]
    invalidateObject = classmethod(invalidateObject)

    def invalidate(self):
        self.invalidateObject(self)
