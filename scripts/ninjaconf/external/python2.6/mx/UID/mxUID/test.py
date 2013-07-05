# -*- coding: latin-1 -*-
import mx.UID
from mx.UID import *

print 'Testing UID version %s ...' % mx.UID.__version__

uid1 = UID()
uid2 = UID()

assert uid1 != uid2
assert verify(uid1) == 1
assert verify(uid2) == 1
assert verify(uid1 + 'abc') == 0
assert verify('abc' + uid2) == 0

key = 'Marc-André Lemburg'
assert mangle(uid1, key) != uid1
assert mangle(uid2, key) != uid2
assert demangle(mangle(uid1, key), key) == uid1
assert demangle(mangle(uid2, key), key) == uid2
assert mangle(demangle(uid1, key), key) == uid1
assert mangle(demangle(uid2, key), key) == uid2

for i in xrange(100): u=UID();print mangle(u,'test'),u

print 'Works.'
