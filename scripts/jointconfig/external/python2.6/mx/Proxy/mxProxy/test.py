from mx import Proxy
import sys

cleaned_up = 0

class DataRecord:
    a = 2
    b = 3
    # Make read-only:
    def __public_setattr__(self,what,to):
        raise Proxy.AccessError,'read-only'
    # Cleanup protocol
    def __cleanup__(self):
        global cleaned_up
        print 'cleaning up',self
        cleaned_up = 1

o = DataRecord()

# Wrap the instance:
p = Proxy.InstanceProxy(o,('a',))
# Remove o from the accessible system:
del o

print 'Read p.a through Proxy:',p.a

# This will cause an exception, because the object is read-only
if 1:
    try:
        p.a = 3
    except:
        pass
    else:
        raise AssertionError,'should be read-only'

# This will cause an exception, because no access is given to .b
if 1:
    try:
        p.b
    except Proxy.AccessError:
        pass
    else:
        raise AssertionError,'should give no access'

# Cleanup error tracebacks by overwriting the previous error;
# this should remove the reference to p in the traceback of the
# previous exception.
if 1:
    try:
        1/0
    except:
        pass

# Deleting the Proxy will also delete the wrapped object, if there
# is no other reference to it in the system. It will invoke
# the __cleanup__ method in that case.
del p
assert cleaned_up

#
# Creating and deleting weak Proxies and their referenced objects
#
d = {}
p = Proxy.WeakProxy(d)
q = Proxy.WeakProxy(d)
del p
del q
del d

d = {}
p = Proxy.WeakProxy(d)
q = Proxy.WeakProxy(d)
del q
del p
del d

d = {}
p = Proxy.WeakProxy(d)
q = Proxy.WeakProxy(d)
del d
del p
del q

d = {}
p = Proxy.WeakProxy(d)
q = Proxy.WeakProxy(d)
del d
del q
del p

d = {}
p = Proxy.WeakProxy(d)
q = Proxy.WeakProxy(d)
del d
Proxy.checkweakrefs()
try:
    p[1]
except Proxy.LostReferenceError:
    pass
else:
    print '*** Phantom object still alive !'

print
print 'Works.'
