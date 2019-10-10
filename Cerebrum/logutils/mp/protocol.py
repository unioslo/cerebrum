# -*- coding: utf-8 -*-
"""
Serializing protocol for sending log records between processes.
"""
from __future__ import print_function, unicode_literals

import json
import logging


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
