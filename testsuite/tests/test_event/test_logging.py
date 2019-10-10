#!/usr/bin/env python
# encoding: utf-8
""" Unit tests for event logging. """
import logging
import pickle
from collections import namedtuple
from functools import partial

import pytest
from six.moves.queue import Empty


@pytest.fixture
def real_logger():
    LogItem = namedtuple('LogItem', ('level', 'msg', 'args', 'kwargs'))

    class LogList(object):
        def __init__(self):
            self._logged_items = []

        def _log(self, level, msg, *args, **kwargs):
            item = LogItem(level, msg, args, kwargs)
            self._logged_items.append(item)

        def __getattribute__(self, name):
            if name in ('_log', '_logged_items'):
                return super(LogList, self).__getattribute__(name)
            return partial(self._log, name)
    return LogList()


@pytest.fixture
def log_queue():
    class _Queue(object):
        def __init__(self):
            self.q = []

        def put(self, item):
            self.q.append(item)

        def get(self, *args, **kwargs):
            try:
                return self.q.pop(0)
            except IndexError:
                raise Empty()
    return _Queue()


@pytest.fixture
def log_proto():
    mod = pytest.importorskip('Cerebrum.logutils.mp.protocol')
    return mod.LogRecordProtocol()


@pytest.fixture
def log_channel(log_queue, log_proto):
    mod = pytest.importorskip('Cerebrum.logutils.mp.channel')
    return mod.QueueChannel(log_queue, log_proto)


@pytest.fixture
def log_handler(log_channel):
    u""" The EventMap module to test. """
    mod = pytest.importorskip('Cerebrum.logutils.mp')
    handler = mod.ChannelHandler(log_channel)
    return handler


def test_log_info(log_queue, log_proto, log_handler):
    record = logging.makeLogRecord({
        'levelno': logging.INFO,
        'levelname': 'INFO',
        'name': 'tests.test_event.test_logging',
        'msg': u'some log message',
        'args': (),
    })
    log_handler.emit(record)
    assert len(log_queue.q) == 1

    item = log_queue.get()
    other = log_proto.deserialize(item)
    assert other.msg == 'some log message'
    assert other.levelno == logging.INFO


def test_log_args(log_queue, log_proto, log_handler):
    record = logging.makeLogRecord({
        'levelno': logging.INFO,
        'levelname': 'INFO',
        'name': 'tests.test_event.test_logging',
        'msg': u'%s %d',
        'args': ('foo', 5),
    })
    log_handler.emit(record)
    assert len(log_queue.q) == 1

    item = log_queue.get()
    other = log_proto.deserialize(item)
    assert other.getMessage() == 'foo 5'


def test_log_args_error(log_queue, log_proto, log_handler):
    record = logging.makeLogRecord({
        'levelno': logging.INFO,
        'levelname': 'INFO',
        'name': 'tests.test_event.test_logging',
        'msg': u'asdf %d %d',
        'args': ('foo', 573),
    })
    log_handler.emit(record)
    assert len(log_queue.q) == 1

    item = log_queue.get()
    other = log_proto.deserialize(item)
    msg = other.getMessage()
    print(repr(msg))
    assert 'asdf' in msg
    assert 'foo' in msg
    assert '573' in msg


def test_logrecord_repr_unpickleable(log_queue, log_proto, log_handler):
    # The items thrown on a multiprocessing queue must be pickleable
    unpickleable = lambda x: x * 2  # noqa: E731
    with pytest.raises(pickle.PicklingError):
        # Make sure it's not pickleable
        pickle.dumps(unpickleable)

    record = logging.makeLogRecord({
        'levelno': logging.INFO,
        'levelname': 'INFO',
        'name': 'tests.test_event.test_logging',
        'msg': u'callable=%r',
        'args': (unpickleable,),
    })

    log_handler.emit(record)
    assert len(log_queue.q) == 1

    item = log_queue.get()
    other = log_proto.deserialize(item)
    msg = other.getMessage()
    assert 'callable' in msg
