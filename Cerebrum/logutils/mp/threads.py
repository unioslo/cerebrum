# -*- coding: utf-8 -*-
"""
Threads for processing and monitoring log record queues.
"""
from __future__ import print_function, unicode_literals

import logging
import threading

from six.moves.queue import Empty


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

    timeout = 3
    """ Timeout for listening on the log queue """

    def __init__(self, queue, protocol, **kwargs):
        """
        :type queue: Queue.Queue
        :type protocol: LogRecordProtocol
        :param logger: deprecated argument

        passes all other kwargs to `threading.Thread.__init__`
        """
        # The logger keyword is deprecated
        kwargs.pop('logger', None)
        self.queue = queue
        self.logger = logging.getLogger(__name__)
        self.protocol = protocol
        super(LogRecordThread, self).__init__(**kwargs)

    def run(self):
        self.logger.info('Logger thread started')
        while not self.is_stopped():
            try:
                message = self.queue.get(block=True, timeout=self.timeout)
            except Empty:
                continue

            try:
                # self.logger.debug('got_message: %r', message)
                record = self.protocol.deserialize(message)
            except Exception:
                self.logger.error("Unable to deserialize record: %r", message,
                                  exc_info=True)
            else:
                lg = logging.getLogger(record.name)
                if lg.isEnabledFor(record.levelno):
                    lg.handle(record)
            finally:
                self.queue.task_done()
        self.logger.info('Logger thread stopped')


class LogMonitorThread(_StoppableThread):
    """ A thread that logs the number of items in a queue.

    If the queue is a `LogQueue` object, some additional behaviour applies:

    - The log message will include a fill ratio (in percent)
    - If the ratio exceeds `threshold_error`, the message will be logged as an
      error
    - If the ratio exceeds `threshold_warning`, the message will be logged as a
      warning.
    """

    threshold_error = 90
    threshold_warning = 75

    def __init__(self,
                 queue,
                 interval,
                 threshold_error=threshold_error,
                 threshold_warning=threshold_warning,
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
        self.logger = logging.getLogger(__name__)
        super(LogMonitorThread, self).__init__(**kwargs)

    def run(self):
        self.logger.info('Queue monitor thread started')
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
                log = self.logger.error
            elif self.threshold_warning and ratio > self.threshold_warning:
                log = self.logger.warning
            else:
                log = self.logger.info

            log('~%s items on the log queue (%d%% full)',
                format(size, ',d'), ratio)
        self.logger.info('Queue monitor thread stopped')
