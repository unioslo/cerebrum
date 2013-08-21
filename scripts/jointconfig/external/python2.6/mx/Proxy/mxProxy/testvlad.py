from mx.Proxy import WeakProxy
o = []
p = q = WeakProxy(o)
p = q = WeakProxy(o)
del o
print p
