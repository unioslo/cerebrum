# -*- coding: utf-8 -*-
#
# Copyright 2019-2026 University of Oslo, Norway
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
"""
Threads for processing and monitoring log record queues.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import logging
import threading

from six.moves.queue import Queue

try:
    from setproctitle import setthreadtitle
except ImportError:
    def setthreadtitle(*args, **kwargs):
        pass

__all__ = (
    "StoppableThread",
    "LogRecordThread",
    "QueueMonitorThread",
    "SizedQueue",
)

logger = logging.getLogger(__name__)


class StoppableThread(threading.Thread):
    """
    Thread mixin to provide stop signalling.

    The threads in this module contain a run-loop that will *block* until a
    *timeout* occurs.  To shutdown cleanly, they use this mixin to provide a
    *stop signal* that tells the thread to shutdown as soon as it stops
    blocking.
    """

    default_name = None
    """
    A default name for this thread.

    This class does not provide a default name, but the attribute allows for a
    default name in subclasses.
    """

    def __init__(self, **kwargs):
        """
        :param str name: Thread name, defaults to :data:`.default_name`
        :param kwargs: Arguments for :class:`threading.Thread`
        """
        name = kwargs.pop('name', self.default_name)
        if name:
            kwargs['name'] = name
        super(StoppableThread, self).__init__(**kwargs)
        self.__stop = threading.Event()

    def stop(self):
        """
        Set a stop signal for this thread.
        """
        self.__stop.set()

    def is_stopped(self, timeout=None):
        """
        Check if stop signal has been set.

        :type timeout: int or float
        :param timeout:
            Optionally block and wait for the stop signal to be set (up to
            *timeout* seconds).

        :rtype: bool
        :returns: if the stop signal has been set
        """
        if timeout is None:
            return self.__stop.is_set()
        else:
            return self.__stop.wait(float(timeout))


class LogRecordThread(StoppableThread):
    """
    Handle log records from a channel.

    This is a logger thread for multiprocessing applications.  The thread
    listens for log records on a given *channel* (see: :mod:`.channel`).

    Log records are handled by the logger indicated by the ``LogRecord.name``.
    This means that the log configuration for the thread's owner process
    decides what to do with this record.
    """

    timeout = 1
    """ Default channel poll rate, in seconds. """

    default_name = "log-queue-proc"
    """ Default thread name. """

    def __init__(self, channel, timeout=timeout, **kwargs):
        """
        :type channel: channel.BaseChannel
        :param channel: Channel for incoming log records

        :type timeout: int or float
        :param timeout:
            Channel poll rate, in seconds.

            While polling the channel, this thread will *block*, which means it
            cannot be *stopped* immediately with ``LogRecordThread.stop()``.

            Set this *low* to reduce the ``thread.join()`` wait time, or *high*
            to reduce the overhead of the thread shutdown mechanism.

        :param kwargs: Passed on to :class:`threading.Thread`
        """
        self.channel = channel
        self.timeout = timeout
        super(LogRecordThread, self).__init__(**kwargs)

    def run(self):
        """ Start processing the channel. """
        logger.info('Logger thread started')
        if self.name:
            setthreadtitle(self.name)
        while not self.is_stopped():
            try:
                record = self.channel.poll(timeout=self.timeout)
            except IOError:
                logger.critical("IPC seems to be broken!", exc_info=True)
                raise
            except Exception:
                logger.error("Unable to receive record", exc_info=True)
                continue

            if record is None:
                continue

            try:
                _log = logging.getLogger(record.name)
                _enabled = _log.isEnabledFor(record.levelno)
                if _enabled:
                    _log.handle(record)
            except Exception:
                logger.error("Unable to log record: %r", record, exc_info=True)
        logger.info('Logger thread stopped')


class QueueMonitorThread(StoppableThread):
    """
    Monitor the size of a queue.

    This thread periodically logs the number of items on a given queue.

    If the queue is a :class:`.SizedQueue` object, the log message will also
    include some extra information:

    - Fill ratio (in percent)
    - If the ratio exceeds `threshold_error`, the message will be logged as an
      error
    - If the ratio exceeds `threshold_warning`, the message will be logged as a
      warning.
    """

    threshold_error = 90
    threshold_warning = 75
    threshold_info = 5

    default_level = logging.DEBUG
    """ Log level for queue sizes below the thresholds. """

    default_name = "log-queue-mon"
    """ Default thread name. """

    def __init__(self, queue, interval,
                 threshold_error=threshold_error,
                 threshold_warning=threshold_warning,
                 threshold_info=threshold_info,
                 **kwargs):
        """
        :type queue: queue.Queue
        :param queue: The queue to monitor

        :type interval: float
        :param interval:
            How often the queue size should be monitored and reported (in
            seconds).

        :type threshold_error: int
        :param threshold_error: Fill ratio threshold for log level ERROR.

        :type threshold_warning: int
        :param threshold_warning: Fill ratio threshold for log level WARNING.

        :type threshold_info: int
        :param threshold_info: Fill ratio threshold for log level INFO.

        :param kwargs: Passed on to :class:`threading.Thread`

        .. note::
           Thresholds only apply when monitoring a :class:`.SizedQueue`.
        """
        self.queue = queue
        self.interval = float(interval)
        self.threshold_error = threshold_error
        self.threshold_warning = threshold_warning
        self.threshold_info = threshold_info
        super(QueueMonitorThread, self).__init__(**kwargs)

    def run(self):
        """ Start monitoring queue size. """
        logger.info('Queue monitor thread started')
        if self.name:
            setthreadtitle(self.name)
        while not self.is_stopped(self.interval):
            size = self.queue.qsize()

            if hasattr(self.queue, 'get_maxsize'):
                maxsize = self.queue.get_maxsize()
            else:
                maxsize = 0

            if maxsize:
                ratio = int(100 * float(size) / float(maxsize))
            else:
                ratio = -1

            if self.threshold_error and ratio > self.threshold_error:
                level = logging.ERROR
            elif self.threshold_warning and ratio > self.threshold_warning:
                level = logging.WARNING
            elif self.threshold_info and ratio > self.threshold_info:
                level = logging.INFO
            else:
                level = self.default_level

            logger.log(
                level,
                '~%s items on the log queue (%d%% full)',
                format(size, ',d'), ratio)
        logger.info('Queue monitor thread stopped')


class SizedQueue(Queue):
    """ A queue.Queue object with access to the maxsize attribute.

    Proxied objects (from a multiprocessing.manager.BaseManager) do not
    expose attributes, only methods. This class exposes the maxsize attribute
    through a method.
    """
    def get_maxsize(self):
        return self.maxsize
