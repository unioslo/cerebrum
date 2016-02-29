#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2015 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
u""" This module contains simple multiprocess logging tools. """
import multiprocessing
import threading
import functools
import Queue
from collections import namedtuple


LogQueueRecord = namedtuple('LogQueueRecord',
                            ('source', 'level', 'msg'))
u""" A Log Record for a shared log queue. """


class QueueLogger(object):
    u""" Logger that simply sticks `LogQueueRecord`s on a queue.

    Typical usage:

    >>> logger = QueueLogger(Queue())
    >>> logger.info(u'Logging an int: %d', 5)
    >>> logger.info(u'Logging an object: %s', repr(object()))

    """

    __slots__ = ('queue', 'source')

    # TODO: Make sure to implement proper logging API
    log_levels = ('debug4', 'debug3', 'debug2', 'debug1', 'debug',
                  'info', 'warn', 'warning', 'error')
    u""" Valid logging methods. """

    def __init__(self, source, log_queue):
        self.source = source
        self.queue = log_queue

    def log(self, level, fmt, *args, **kwargs):
        u""" Put log record on queue.

        :param str level:
            Logging level for the log record.
        :param str fmt:
            Message of the log record.
        :param *list args:
            Positional arguments (replace values) for the `msg`.
        :param **dict kwargs:
            Named arguments (replace values) for the `msg`.
        """
        if self.queue is None:
            # TODO: Raise error? Handle better?
            return
        if args or kwargs:
            try:
                msg = fmt.format(*args, **kwargs)
            except Exception as e:
                msg = (u'Unable to format record (msg={!r}, args={!r},'
                       u' kwargs={!r}, reason={!s})'.format(fmt, args,
                                                            kwargs, e))
        else:
            msg = fmt
        self.queue.put(LogQueueRecord(self.source, level, msg))

    def __getattribute__(self, attr):
        if attr in type(self).log_levels:
            return functools.partial(self.log, attr)
        return super(QueueLogger, self).__getattribute__(attr)


class LoggerThread(threading.Thread):
    u""" A thread for listening on a Queue with LogQueueRecords. """

    timeout = 5
    u""" Timeout for listening on the log queue """
    # TODO: Should this thread create and own a Queue?

    def __init__(self, logger=None, queue=None, **kwargs):
        u""" Create a new Queue listener.

        :param Logger logger:
            Logger implementation to log the actual messages to.

        :param Queue queue:
            Queue to listen for LogQueueRecords on.

        :param **dict kwargs:
            Keyword arguments to threading.Thread.

        """
        self.logger = logger
        self.queue = queue
        self.__run_logger = True
        super(LoggerThread, self).__init__(**kwargs)

    def stop(self):
        self.__run_logger = False

    def _log(self, lvl, fmt, *args, **kwargs):
        u""" Log to the real logger, with self as source. """
        fmt = u'[{!s}] {!s}'.format(self.name, fmt)
        if not self.logger:
            # print lvl, fmt, repr(args), repr(kwargs)
            # Initialize and use the mp stderr logger?
            return
        log = getattr(self.logger, lvl)
        log(fmt, *args, **kwargs)

    @property
    def queue(self):
        u""" The log queue. """
        if not self._queue:
            self._queue = Queue()
        return self._queue

    @queue.setter
    def queue(self, queue):
        self._queue = queue

    def run(self):
        self._log('info', u'Logger thread started')
        while self.__run_logger:
            try:
                entry = self.queue.get(block=True, timeout=self.timeout)
            except Queue.Empty:
                continue
            if not isinstance(entry, LogQueueRecord):
                self._log('warn', u'Invalid log record: %r (type=%s)',
                          entry, type(entry))
                continue
            try:
                log = getattr(self.logger, entry.level)
            except AttributeError:
                self._log('warn', u'Invalid level %r in log record (%r)',
                          entry.level, entry)
                continue

            try:
                msg = u'[{!s}] {!s}'.format(entry.source, entry.msg)
                log(msg)
            except Exception as e:
                self._log('error', u'Unable to log entry %r: %s', entry, e)
        self._log('info', u'Logger thread stopped')


def get_stderr_logger(level=multiprocessing.SUBDEBUG):
    lug = multiprocessing.log_to_stderr()
    lug.setLevel(level)
    return lug
