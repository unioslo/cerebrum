# -*- coding: ISO8859-1 -*-
#
# Copyright (c) 2004, Erik Gorset. All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met: Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
# Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution.
# Neither the name of NTNU nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

""" A generator based scheduler

$Id$
Erik Gorset, erikgors@stud.ntnu.no

examples:

def example():
    yield WAIT, 10 #tell the scheduler to wait for 10 seconds
    a = 1 + 1 # do something
    yield WAIT, 2 #wait for another 2 seconds
    print 'finnished'

sched = YScheduler()
sched.add(example())
sched.run()
"""

from __future__ import generators

import time
import select
import traceback
import sys
import Queue
import signal

NOTHING     = 0
READ        = 1
WRITE       = 2
EXCEPTION   = 3
WAIT        = 4
TIMEOUT     = 5
NEW         = 6

class YScheduler:
    NOTHING     = NOTHING
    READ        = READ
    WRITE       = WRITE
    EXCEPTION   = EXCEPTION
    WAIT        = WAIT
    TIMEOUT     = TIMEOUT
    NEW         = NEW

    addMap = {}

    def __init__(self):
        self.queue = Queue.Queue()
        self.timeout = Queue.Queue()
        self.waitlist = []

        self.rlist = {}
        self.wlist = {}
        self.xlist = {}

        def internal():
            while 1:
                yield NOTHING
                if self.rlist or self.wlist or self.xlist:
                    self._checkSelect()
                    yield NOTHING
                next = self._next()
                while next is None or next > 0.05:
                    time.sleep(0.05)
                    next = self._next()
                if next > 0:
                    time.sleep(next)
                self._checkWait()
        self.queue.put(internal())

    def add(self, gen, action=None, obj=None):
        if not hasattr(gen, 'next'):
            raise TypeError("gen has no next method")

        if action in self.addMap:
            addMap[action](gen, action, obj)

        elif action == WAIT:
            self.waitlist.append((time.time() + obj, gen))
            self.waitlist.sort()

        elif action == READ:
            self.rlist[obj] = gen

        elif action == WRITE:
            self.wlist[obj] = gen

        elif action == EXCEPTION:
            self.xlist[obj] = gen

        elif action == TIMEOUT:
            self.timeout.put((gen, obj))

        elif action == NEW:
            self.queue.put(obj)
            self.queue.put(gen)

        else:
            self.queue.put(gen)

    def addTimer(self, delay, function, *args, **vargs):
        assert type(delay) == int
        def gen():
            yield self.WAIT, delay
            function(*args,**vargs)
        self.queue.put(gen())

    def _work(self, gen):
        try:
            result = gen.next()
            if result:
                action, obj = result
            else:
                action = None
                obj = None
        except StopIteration:
            pass
        except SystemExit, e:
            raise SystemExit, e
        except:
            traceback.print_exc()
        else:
            self.add(gen, action, obj)

    def workTimeout(self):
        try:
            gen, timeout = self.timeout.get_nowait()
        except Queue.Empty:
            self.work()
        else:
            def handler(signum, frame):
                print 'Signal handler called with signal', signum
                raise Exception('Timeout for %s after %s seconds' % (gen, timeout))

            signal.signal(signal.SIGALRM, handler)
            signal.alarm(timeout)
            self._work(gen)
            signal.alarm(0)
            
    def work(self):
        gen = self.queue.get()
        self._work(gen)

    def _checkWait(self):
        now = time.time()
        while self.waitlist and now >= self.waitlist[0][0]:
            gen = self.waitlist[0][1]
            del self.waitlist[0]
            self.queue.put(gen)

    def _next(self):
        if self.queue.qsize():
            return 0
        elif self.waitlist:
            return self.waitlist[0][0] - time.time()
        else:
            return None

    def _checkSelect(self):
        rkeys = self.rlist.keys()
        wkeys = self.wlist.keys()
        xkeys = self.xlist.keys()
        try:
            r, w, x = select.select(rkeys, wkeys, xkeys, self._next())
        except:
            traceback.print_exc()
            # do work on all bad filedescriptors
            check = lambda i:type(i) and i == -1 or i.fileno() == -1
            r = [i for i in rkeys if check(i)]
            w = [i for i in wkeys if check(i)]
            x = [i for i in xkeys if check(i)]
        for socks,l in (r,self.rlist),(w,self.wlist),(x,self.xlist):
            for i in socks:
                gen = l[i]
                del l[i]
                self.queue.put(gen)

    def run(self, workTimeout=False):
        if workTimeout:
            while 1:
                self.workTimeout()
        else:
            while 1:
                self.work()

def test():
    def wait(id):
        print id, 'waiting 5 sec'
        yield WAIT, 5 # tell the scheduler to wait for 10 seconds
        a = 1 + 1 # do something
        print id, 'a =', a
        yield WAIT, 2 # wait for another 2 seconds
        print id, 'finnished'

    def timeout(id, timeout, sleep):
        yield TIMEOUT, timeout
        print id, 'timeout set to', timeout
        print id, 'sleeping for %s' % sleep
        time.sleep(sleep)
        print id, 'finnished'

    sched = YScheduler()
    sched.add(wait('[1]'))
    sched.add(timeout('[2]', 1, 0.5))
    sched.add(timeout('[3]', 3, 4))
    sched.add(timeout('[4]', 5, 2))
    import thread
    thread.start_new_thread(sched.run,())
    thread.start_new_thread(sched.run,())
    thread.start_new_thread(sched.run,())
    sched.run(True)

def test2():
    def wait():
        print 'finnished!'

    sched = YScheduler()
    import thread
    thread.start_new_thread(sched.run, ())
    sched.addTimer(5, wait)
    time.sleep(6)

if __name__ == '__main__':
    test()
