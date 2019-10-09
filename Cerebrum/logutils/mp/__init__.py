# -*- encoding: utf-8 -*-
#
# Copyright 2015-2019 University of Oslo, Norway
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
This module contains simple multiprocess logging tools.
"""
from __future__ import print_function

import Queue
import json
import logging
import multiprocessing
import threading


class LogRecordSerializer(object):

    @staticmethod
    def dumps(record_dict):
        raise NotImplementedError("")

    @staticmethod
    def loads(record_dict):
        raise NotImplementedError("")


class JsonSerializer(LogRecordSerializer):
    """ JSON serializer, for use LogRecordProtocol. """

    @staticmethod
    def dumps(record_dict):
        return json.dumps(record_dict)

    @staticmethod
    def loads(data):
        # JSON serializes tuples as lists, but string formatting
        # expects `LogRecord.args` to be a tuple or a dict
        dct = json.loads(data)
        if isinstance(dct.get('args'), list):
            dct['args'] = tuple(dct['args'])

        # exc_info is also a tuple if set, let's keep it that way
        if isinstance(dct.get('exc_info'), list):
            dct['exc_info'] = tuple(dct['exc_info'])
        return dct


class LogRecordProtocol(object):
    """ Serialize and Deserialize LogRecord objects. """

    serializer = JsonSerializer()

    def __init__(self, serializer=serializer):
        """
        :param object serializer:
            an object with callable attributes `dumps` and `loads`
        """
        self.serializer = serializer

    def _format_exc(self, exc_info):
        """ helper - format exc info into a serializeable text. """
        formatter = logging.Formatter()
        return formatter.formatException(exc_info)

    def _format_error(self, record_dict, reason, e):
        """ helper - format a log message on errors.

        This typically occurs if:
        - the log message format is invalid or is given wrong number of args
        - the message args contains unserializable values
        """
        reason = reason or 'LogRecordProtocol serialize error'
        msg = '{reason}: msg=%s args=%s error=%s'.format(reason=reason)
        record_dict['args'] = (repr(record_dict['msg']),
                               repr(record_dict['args']),
                               repr(e))
        record_dict['msg'] = msg

    def serialize(self, log_record):
        """ Serialize a log record.

        :param logging.LogRecord log_record:
            The log record, as sent to `logging.Logger.handle`.
        """
        record_dict = dict(log_record.__dict__)

        # Let's make sure that we can actually format the log message here
        #
        # TODO: We may want to hook into the regular logger error handling here
        # if the formatting fails?
        try:
            log_record.getMessage()
        except Exception as e:
            self._format_error(record_dict, 'Unable to format log record',  e)

        # Pretty much nothing can serialize tracebacks...  Let's pre-format
        # tracebacks if they are present.
        #
        # This is not ideal, as the receiving handlers and formatters may
        # define their own traceback format.  That is an exceptionally rare
        # thing to do though...
        if record_dict['exc_info']:
            record_dict['exc_text'] = self._format_exc(record_dict['exc_info'])
            record_dict['exc_info'] = (repr(record_dict['exc_info'][0]),
                                       repr(record_dict['exc_info'][1]),
                                       None)

        # Let's pre-format the message if it contains unserializable args.
        #
        # This will break log handlers that depends on the LogRecord remaining
        # unaltered (e.g. raven and grouping of log records in sentry). There's
        # really no way around this though...
        #
        # TODO: Try to format msg with a serialized-deserialized args list?
        try:
            self.serializer.dumps(record_dict['args'])
        except Exception as e:
            self._format_error(record_dict, 'Unable to serialize args', e)
        return self.serializer.dumps(record_dict)

    def deserialize(self, data):
        """ Deserialize a log record.

        :return logging.LogRecord:
            Returns a log record object.
        """
        return logging.makeLogRecord(self.serializer.loads(data))


class LogQueue(Queue.Queue):
    """ A Queue.Queue object with access to the maxsize attribute.

    Proxied objects (from a multiprocessing.manager.BaseManager) does not
    expose attributes, only methods. This class exposes the maxsize attribute
    through a method.
    """
    def get_maxsize(self):
        return self.maxsize


class QueueHandler(logging.Handler):
    """ Handler that sticks serialized `LogRecord` dicts onto a queue. """

    protocol = LogRecordProtocol()

    def __init__(self, queue, protocol=protocol):
        """
        :type queue: Queue.Queue
        :type protocol: LogRecordProtocol
        """
        if queue is None:
            raise ValueError("Invalid queue")
        self.protocol = protocol
        self.queue = queue
        super(QueueHandler, self).__init__()

    def send(self, s):
        # TODO: Copy error handling from logging.handlers.SocketHandler?
        self.queue.put(s)

    def emit(self, record):
        try:
            s = self.protocol.serialize(record)
            self.send(s)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)

    def close(self):
        pass


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

    protocol = LogRecordProtocol()

    timeout = 3
    """ Timeout for listening on the log queue """

    def __init__(self, queue, protocol=protocol, **kwargs):
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
            except Queue.Empty:
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


def get_stderr_logger(level=multiprocessing.SUBDEBUG):
    lug = multiprocessing.log_to_stderr()
    lug.setLevel(level)
    return lug
