import sys
import mx.Proxy

class Object:
   def __init__(self, id):
      self.id = id
   def __del__(self):
      print self.id, 'deleted'
   def __repr__(self):
      return '<Object %s at %d (0x%x)>' % (self.id, id(self), id(self))

def  test():
   x = Object('first')
   x.y = Object('second')
   x.y.x = mx.Proxy.WeakProxy(x)

test()

# if I uncomment the following, everything works as expected, which suggests
# to me that either the WeakReferences dictionary is not getting GC'd
#y = x.y
#del x
#print y.x.id
