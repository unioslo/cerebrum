import sys, random, os
from mx.BeeBase.BeeIndex import *

### Settings

testfile = 'beebase.idx'
count = 1000

### Test BeeIndex

print 'Building integer index without duplicates...',
idx = BeeIntegerIndex(testfile, dupkeys=0, filemode=2)
for i in xrange(count):
    try:
        idx[i] = i+1
    except:
        print ' Problem for key %i: %s' % (i, sys.exc_info()[1])
idx.flush()
idx.close()
print 'done.'

print 'Checking integer index without duplicates...',
idx = BeeIntegerIndex(testfile, dupkeys=0, filemode=3)
for i in xrange(count):
    try:
        if idx[i] != i+1:
            print ' key %i corrupt' % i
    except:
        print ' Problem for key %i: %s' % (i, sys.exc_info()[1])
idx.flush()
idx.close()
print 'done.'

print 'Building string index without duplicates...',
idx = BeeStringIndex(testfile, keysize=10, dupkeys=0, filemode=2)
for i in xrange(count):
    try:
        idx[str(i)] = i+1
    except:
        print ' Problem for key %i: %s' % (i, sys.exc_info()[1])
idx.flush()
idx.close()
print 'done.'

print 'Checking string index without duplicates...',
idx = BeeStringIndex(testfile, keysize=10, dupkeys=0, filemode=3)
for i in xrange(count):
    try:
        if idx[str(i)] != i+1:
            print ' key %i corrupt' % i
    except:
        print ' Problem for key %i: %s' % (i, sys.exc_info()[1])
idx.flush()
idx.close()
print 'done.'

print 'Building fixed length string index without duplicates...',
idx = BeeFixedLengthStringIndex(testfile, keysize=10, dupkeys=0, filemode=2)
for i in xrange(count):
    try:
        idx['%010i' % i] = i+1
    except:
        print ' Problem for key %i: %s' % (i, sys.exc_info()[1])
idx.flush()
idx.close()
print 'done.'

print 'Checking fixed length string index without duplicates...',
idx = BeeFixedLengthStringIndex(testfile, keysize=10, dupkeys=0, filemode=3)
for i in xrange(count):
    try:
        if idx['%010i' % i] != i+1:
            print ' key %i corrupt' % i
    except:
        print ' Problem for key %i: %s' % (i, sys.exc_info()[1])
idx.flush()
idx.close()
print 'done.'

###

print 'Building integer index with duplicates...',
idx = BeeIntegerIndex(testfile, dupkeys=0, filemode=2)
for i in xrange(count):
    try:
        idx[i] = i+1
        idx[i] = i+2
    except:
        print ' Problem for key %i: %s' % (i, sys.exc_info()[1])
idx.flush()
idx.close()
print 'done.'

print 'Checking integer index with duplicates...',
idx = BeeIntegerIndex(testfile, dupkeys=0, filemode=3)
for i in xrange(count):
    try:
        v = idx[i]
        if v not in (i+1, i+2):
            print ' key %i corrupt' % i
    except:
        print ' Problem for key %i: %s' % (i, sys.exc_info()[1])
idx.flush()
idx.close()
print 'done.'

print 'Building string index with duplicates...',
idx = BeeStringIndex(testfile, keysize=10, dupkeys=0, filemode=2)
for i in xrange(count):
    try:
        idx[str(i)] = i+1
        idx[str(i)] = i+2
    except:
        print ' Problem for key %i: %s' % (i, sys.exc_info()[1])
idx.flush()
idx.close()
print 'done.'

print 'Checking string index with duplicates...',
idx = BeeStringIndex(testfile, keysize=10, dupkeys=0, filemode=3)
for i in xrange(count):
    try:
        v = idx[str(i)]
        if v not in (i+1, i+2):
            print ' key %i corrupt' % i
    except:
        print ' Problem for key %i: %s' % (i, sys.exc_info()[1])
idx.flush()
idx.close()
print 'done.'

###

idx = BeeStringIndex(testfile, 10)

# Insert some data
for i in range(1000):
        key = str(random.random())[:10]
        idx[key] = i

idx.close()

# Reopen read-only
idx = BeeStringIndex(testfile, 10, filemode=1)

# Walk the idx with a cursor
up = idx.cursor(FirstKey)
down = idx.cursor(LastKey)
i = 0
while 1:
        if i % 100 == 0:
                print '%5i: up %10s:%5s -- down %10s:%5s' % \
                      (i, up.key, up.value, down.key, down.value)
        i = i + 1
        if not up.next():
                break
        if not down.prev():
                break
print '%5i: up %10s:%5s -- down %10s:%5s' % \
      (i, up.key, up.value, down.key, down.value)

print 'Found %i keys' % i

idx.close()

os.remove(testfile)

### Test BeeDicts

from mx.BeeBase.BeeDict import *

print 'Testing BeeStringDict...',

s = BeeStringDict(testfile)
s['foo']='bar'
assert s['foo'] == 'bar'
s.commit()
s.close()

s = BeeStringDict(testfile)
assert s['foo'] == 'bar'
s.close()

s = BeeStringDict(testfile)
assert s['foo'] == 'bar'
s['foo']='test'
assert s['foo'] == 'test'
s['foo1']='test1'
assert s['foo1'] == 'test1'
s.commit()
s.close()

s = BeeStringDict(testfile)
assert s['foo'] == 'test'
assert s['foo1'] == 'test1'
s.commit()
s.close()

s.remove_files()

print 'done.'

###

print 'Testing BeeStringDict with keysize 99...',

s = BeeStringDict(testfile, keysize=99)
s['foo']='bar'
assert s['foo'] == 'bar'
s.commit()
s.close()

s = BeeStringDict(testfile, keysize=99)
assert s['foo'] == 'bar'
s.close()

s = BeeStringDict(testfile, keysize=99)
assert s['foo'] == 'bar'
s['foo']='test'
assert s['foo'] == 'test'
s['foo1']='test1'
assert s['foo1'] == 'test1'
s.commit()
s.close()

s = BeeStringDict(testfile, keysize=99)
assert s['foo'] == 'test'
assert s['foo1'] == 'test1'
s.commit()
s.close()

s.remove_files()

print 'done.'

###

print 'Testing BeeDict...',

s = BeeDict(testfile)
s['foo']='bar'
assert s['foo'] == 'bar'
s.commit()
s.close()

s = BeeDict(testfile)
assert s['foo'] == 'bar'
s.close()

s = BeeDict(testfile)
assert s['foo'] == 'bar'
s['foo']='test'
assert s['foo'] == 'test'
s['foo1']='test1'
assert s['foo1'] == 'test1'
s.commit()
s.close()

s = BeeDict(testfile)
assert s['foo'] == 'test'
assert s['foo1'] == 'test1'
s.commit()
s.close()

s.remove_files()

print 'done.'

###

print 'Works.'
