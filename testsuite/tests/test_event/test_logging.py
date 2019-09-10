#!/usr/bin/env python
# encoding: utf-8
""" Unit tests for event logging. """
import logging
import pickle
from Queue import Empty
from collections import namedtuple
from functools import partial

import pytest



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
def queue():
    class _queue(object):
        def __init__(self):
            self.q = []

        def put(self, item):
            self.q.append(item)

        def get(self, *args, **kwargs):
            try:
                return self.q.pop(0)
            except IndexError:
                raise Empty()
    return _queue()


@pytest.fixture
def logutils():
    return pytest.importorskip('Cerebrum.modules.event.logutils')


@pytest.fixture
def queue_handler(logutils, queue):
    u""" The EventMap module to test. """
    queue_handler = logutils.QueueHandler(queue)
    return queue_handler


@pytest.fixture
def log_thread(logutils, real_logger, queue):
    return logutils.LoggerThread(logger=real_logger, queue=queue)


def test_log_info(queue, queue_handler):
    record = logging.makeLogRecord({
        'levelno': logging.INFO,
        'levelname': 'INFO',
        'name': 'tests.test_event.test_logging',
        'msg': u'some log message',
        'args': (),
    })
    queue_handler.emit(record)
    assert len(queue.q) == 1

    item = queue.get()
    other = queue_handler.protocol.deserialize(item)
    assert other.msg == 'some log message'
    assert other.levelno == logging.INFO


def test_log_args(queue, queue_handler):
    record = logging.makeLogRecord({
        'levelno': logging.INFO,
        'levelname': 'INFO',
        'name': 'tests.test_event.test_logging',
        'msg': u'%s %d',
        'args': ('foo', 5),
    })
    queue_handler.emit(record)
    assert len(queue.q) == 1

    item = queue.get()
    other = queue_handler.protocol.deserialize(item)
    assert other.getMessage() == 'foo 5'


def test_log_args_error(queue, queue_handler):
    record = logging.makeLogRecord({
        'levelno': logging.INFO,
        'levelname': 'INFO',
        'name': 'tests.test_event.test_logging',
        'msg': u'asdf %d %d',
        'args': ('foo', 573),
    })
    queue_handler.emit(record)
    assert len(queue.q) == 1

    item = queue.get()
    other = queue_handler.protocol.deserialize(item)
    msg = other.getMessage()
    print(repr(msg))
    assert 'asdf' in msg
    assert 'foo' in msg
    assert '573' in msg


def test_logrecord_repr_unpickleable(queue, queue_handler):
    # The items thrown on a multiprocessing queue must be pickleable
    unpickleable = lambda x: x * 2
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

    queue_handler.emit(record)
    assert len(queue.q) == 1

    item = queue.get()
    other = queue_handler.protocol.deserialize(item)
    msg = other.getMessage()
    assert 'callable' in msg
