#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2015-2017 University of Oslo, Norway
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
""" This module contains simple multiprocess logging tools. """
import json
import logging
import multiprocessing
import Queue
import threading


class LogRecordProtocol(object):
    """ Serialize and Deserialize LogRecord objects. """

    def serialize(self, log_record):
        """ Serialize a log record.

        :param logging.LogRecord log_record:
            The log record, as sent to `logging.Logger.handle`.
        """
        record_dict = dict(log_record.__dict__)
        # Serialize the message args
        try:
            msg = log_record.getMessage()
        except TypeError:
            msg = ('Unable to format: msg={msg!r}'
                   ' args={args!r}').format(**record_dict)
        record_dict['msg'] = msg
        record_dict['args'] = None
        return record_dict

    def deserialize(self, record_dict):
        """ Deserialize a log record.

        :return logging.LogRecord:
            Returns a log record object.
        """
        return logging.makeLogRecord(record_dict)


class JsonSerializer(LogRecordProtocol):
    """ JSON serializer, for use with QueueHandler. """

    def serialize(self, log_record):
        record_dict = super(JsonSerializer, self).serialize(log_record)
        return json.dumps(record_dict)

    def deserialize(self, json_string):
        record_dict = json.loads(json_string)
        return super(JsonSerializer, self).deserialize(record_dict)


class QueueHandler(logging.Handler):
    """ Handler that sticks serialized `LogRecord` dicts onto a queue. """

    def __init__(self, queue, serializer=None):
        if queue is None:
            raise ValueError("Invalid queue")
        if serializer is None:
            self.serializer = JsonSerializer()
        else:
            self.serializer = serializer
        self.queue = queue
        super(QueueHandler, self).__init__()

    def send(self, s):
        # TODO: Copy error handling from logging.handlers.SocketHandler?
        self.queue.put(s)

    def emit(self, record):
        try:
            s = self.serializer.serialize(record)
            self.send(s)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)

    def close(self):
        pass


class LogRecordThread(threading.Thread):
    """ A thread for listening on a Queue with serialized LogRecords. """

    timeout = 5
    """ Timeout for listening on the log queue """

    def __init__(self, queue=None, logger=None, serializer=None, **kwargs):
        """ Create a new Queue listener.

        :param Logger logger:
            Logger implementation to handle actual messages.

        :param Queue queue:
            Queue to listen for log records on.

        :param LogRecordProtocol serializer:
            A de-serializer for log records. This needs to be the same
            implementation used with the QueueHandler that queues log records.

        :param **dict kwargs:
            Keyword arguments to threading.Thread.

        """
        if queue is None:
            raise ValueError("Invalid queue")
        self.queue = queue
        # TODO: This logger is passed in to support 'Cerebrum.modules.cerelog'
        self.__logger = logger
        self.serializer = serializer or JsonSerializer()
        self.__run_logger = True
        super(LogRecordThread, self).__init__(**kwargs)

    @property
    def logger(self):
        return self.__logger or logging.getLogger(__name__)

    def stop(self):
        self.__run_logger = False

    def run(self):
        self.logger.info('Logger thread started')
        while self.__run_logger:
            try:
                message = self.queue.get(block=True, timeout=self.timeout)
            except Queue.Empty:
                continue
            try:
                record = self.serializer.deserialize(message)
            except Exception:
                self.logger.error("Unable to deserialize record: %r", message)
                continue

            if self.__logger:
                # TODO: Remove this when all the multiprocessing daemons are
                # using 'Cerebrum.logutils'
                self.__logger.handle(record)
            else:
                l = logging.getLogger(record.name)
                l.handle(record)
        self.logger.info('Logger thread stopped')


def get_stderr_logger(level=multiprocessing.SUBDEBUG):
    lug = multiprocessing.log_to_stderr()
    lug.setLevel(level)
    return lug
