# -*- encoding: utf-8 -*-
#
# Copyright 2015-2026 University of Oslo, Norway
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
Marshalling of log records.

This module contains utilities for serializing and deserializing
:class:`~logging.LogRecord` objects, so they can be sent over a *channel* to
another process.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import json
import logging
import pickle


class LogRecordSerializer(object):
    """
    Abstract implementation of a marshalling format.
    """

    @staticmethod
    def dumps(record_dict):
        raise NotImplementedError("")

    @staticmethod
    def loads(record_dict):
        raise NotImplementedError("")


class JsonSerializer(LogRecordSerializer):
    """
    JSON serializer for the :class:`.LogRecordProtocol`.
    """

    @staticmethod
    def dumps(record_dict):
        """
        :param dict record_dict: representation of a log record

        :rtype: str
        :returns: A JSON-serialized record dict
        """
        return json.dumps(record_dict)

    @staticmethod
    def loads(data):
        """
        :param str data: A JSON-serialized record dict

        :rtype: dict
        :returns: representation of a log record
        """
        # JSON serializes tuples as lists, but string formatting
        # expects `LogRecord.args` to be a tuple or a dict
        dct = json.loads(data)
        if isinstance(dct.get('args'), list):
            dct['args'] = tuple(dct['args'])

        # exc_info should also be a tuple if set
        if isinstance(dct.get('exc_info'), list):
            dct['exc_info'] = tuple(dct['exc_info'])
        return dct


class PickleSerializer(LogRecordSerializer):
    """
    Pickle serializer for the :class:`.LogRecordProtocol`.
    """

    @staticmethod
    def dumps(record_dict):
        """
        :param dict record_dict: representation of a log record

        :rtype: str
        :returns: A pickled record dict
        """
        return pickle.dumps(record_dict)

    @staticmethod
    def loads(data):
        """
        :param str data: A pickled record dict

        :rtype: dict
        :returns: representation of a log record
        """
        return pickle.loads(data)


class LogRecordProtocol(object):
    """
    Serialize and deserialize log records.
    """

    def __init__(self, serializer):
        """
        :type serializer: LogRecordSerializer
        :param serializer:
            Serializer for deciding message format (e.g. JSON, pickle)
        """
        self.serializer = serializer

    def _format_exc(self, exc_info):
        """ helper - format exc info into a serializable text. """
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
        """
        Serialize a log record.

        .. note::
            Not all log records survive being serialized and de-serialized.

            Notably, exceptions will be replaced by a pre-formatted message, as
            tracebacks cannot be serialized.

            Records with an invalid *msg* format, or *args* that can't be
            marshalled with the chosen *serializer* will get an alternative log
            message with ``repr()``-ed *args* and *msg*

        :type log_record: logging.LogRecord
        :param log_record:
            The log record, as sent to :meth:`logging.Logger.handle`.

        :rtype: str
        :returns: A serialized copy of the log record
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

        # Tracebacks cannot be serialized by most serializers.  Pre-format
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
        # This will break log handlers that depend on the LogRecord remaining
        # unaltered (e.g. raven and grouping of log records in sentry).  There
        # is no way to avoid this.
        #
        # TODO: Try to format msg with a serialized-deserialized args list?
        try:
            self.serializer.dumps(record_dict['args'])
        except Exception as e:
            self._format_error(record_dict, 'Unable to serialize args', e)
        return self.serializer.dumps(record_dict)

    def deserialize(self, data):
        """ Deserialize a log record.

        :param str data: A serialized log record

        :rtype: logging.LogRecord
        :returns: A re-constructed log record.
        """
        return logging.makeLogRecord(self.serializer.loads(data))
