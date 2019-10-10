# -*- coding: utf-8 -*-
"""
Threads for processing and monitoring log record queues.
"""
from __future__ import print_function, unicode_literals

import logging
import threading

logger = logging.getLogger(__name__)


class _StoppableThread(threading.Thread):

    def __init__(self, **kwargs):
        super(_StoppableThread, self).__init__(**kwargs)
        self.__stop = threading.Event()

    def stop(self):
        self.__stop.set()

    def is_stopped(self, timeout=None):
        if timeout is None:
            return self.__stop.is_set()
        else:
            return self.__stop.wait(float(timeout))


class LogRecordThread(_StoppableThread):
    """ A thread for listening on a Queue with serialized LogRecords. """

    timeout = 1
    """ Timeout for listening on the log queue """

    def __init__(self, channel, timeout=timeout, **kwargs):
        """
        :type channel: LogRecordProtocol

        passes all other kwargs to `threading.Thread.__init__`
        """
        # The logger keyword is deprecated
        self.channel = channel
        self.timeout = timeout
        super(LogRecordThread, self).__init__(**kwargs)

    def run(self):
        logger.info('Logger thread started')
        while not self.is_stopped():
            try:
                record = self.channel.poll(timeout=self.timeout)
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


class QueueMonitorThread(_StoppableThread):
    """
    A thread that logs the number of items on a queue.

    If the queue is a `LogQueue` object, some additional behaviour applies:

    - The log message will include a fill ratio (in percent)
    - If the ratio exceeds `threshold_error`, the message will be logged as an
      error
    - If the ratio exceeds `threshold_warning`, the message will be logged as a
      warning.
    """

    threshold_error = 90
    threshold_warning = 75
    threshold_info = 5

    default_level = logging.DEBUG

    def __init__(self,
                 queue,
                 interval,
                 threshold_error=threshold_error,
                 threshold_warning=threshold_warning,
                 threshold_info=threshold_info,
                 **kwargs):
        """
        :type queue: Queue.Queue
        :type interval: float
        :type threshold_error: int
        :type threshold_warning: int

        passes all other kwargs to `threading.Thread.__init__`
        """
        self.queue = queue
        self.interval = float(interval)
        self.threshold_error = threshold_error
        self.threshold_warning = threshold_warning
        self.threshold_info = threshold_info
        super(QueueMonitorThread, self).__init__(**kwargs)

    def run(self):
        logger.info('Queue monitor thread started')
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
