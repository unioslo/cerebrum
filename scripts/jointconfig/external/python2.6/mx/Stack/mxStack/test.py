import sys
from mx.Stack import *

def test():

    s = Stack()
    print repr(s)
    s = Stack()
    for i in range(1000):
          s.push(i)
    while s:
          print s.pop(),

    # which could also be done as:
    s = StackFromSequence(range(1000))
    while s:
          print s.pop(),

    # or a little different
    s = StackFromSequence(range(1000))
    print s.as_tuple()
    print s.as_list()
    print

    print 'Pop many.'
    assert s.pop_many(3) == (999, 998, 997)

    print 'Push many.'
    s.push_many(range(100))
    assert s.pop_many(100) == tuple(range(100-1,-1,-1))

    print 'Resize.'
    assert len(s) > 0
    s.resize()

    print 'Clear.'
    s.clear()
    assert len(s) == 0

    print 'Non-zero testing.'
    s.push_many(range(100))
    i = 0
    while s:
        s.pop()
        i = i + 1
    assert i == 100

    # push many + exceptions
    print 'Push many and exceptions.'
    class C:
        def __getitem__(self,i):
            if i < 50:
                return i + 1
            else:
                raise IndexError
        def __len__(self):
            return 100
    l = C()

    try:
        s.push_many(l)
    except IndexError:
        pass
    else:
        raise AssertionError,'push_many() does not handle errors correctly'

    assert len(s) == 0

    del s

    # Index access
    print 'Index access.'
    s = StackFromSequence(range(1000))
    for i in range(1000):
        assert s[i] == i
    for i in range(1000):
        assert s[-i-1] == 999-i
    i = 0
    for x in s:
        assert x == i
        i = i + 1

    del s

    # Implementation deleaked up to this line.

    print
    print 'Works.'

if '-m' in sys.argv:
    while 1:
        test()
else:
    test()


