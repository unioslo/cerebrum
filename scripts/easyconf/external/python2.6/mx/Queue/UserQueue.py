""" A pure Python Queue implementation modelled after mxQueue.

    Copyright (c) 2000, Marc-Andre Lemburg; mailto:mal@lemburg.com
    Copyright (c) 2000-2008, eGenix.com Software GmbH; mailto:info@egenix.com
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.
"""

__version__ = '0.1'

class UserQueue:

    def __init__(self):

        self.queue = []
        self.headindex = 0

    def push(self,x):

        self.queue.append(x)

    def pop(self):

        headindex = self.headindex
        queue = self.queue
        x = queue[headindex]
        queue[headindex] = None # del. reference
        headindex = headindex + 1
        if headindex > 100  and headindex > len(queue) / 2:
            # compactify
            self.queue = self.queue[headindex:]
            self.headindex = 0
        else:
            self.headindex = headindex
        return x

    def not_empty(self):

        return self.headindex != len(self.queue)

    def head(self):

        return self.queue[self.headindex]

    def tail(self):

        return self.queue[-1]

    def __len__(self):

        return len(self.queue) - self.headindex

    def __repr__(self):

        l = self.queue[self.headindex:]
        l.reverse()
        return '<UserQueue [%s]>' % repr(l)[1:-1]

    def __str__(self):

        l = self.queue[self.headindex:]
        l.reverse()
        return 'q' + repr(l)
