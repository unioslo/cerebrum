#!/usr/bin/env python
# encoding: utf-8
""" Unit tests for event logging. """
import pytest

import pickle

from Queue import Empty
from collections import namedtuple
from functools import partial


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
def queue_logger(logutils, queue):
    u""" The QueueLogger module to test. """
    return logutils.QueueLogger('test', queue)


@pytest.fixture
def log_thread(logutils, real_logger, queue):
    return logutils.LoggerThread(logger=real_logger, queue=queue)


def test_log_info(queue, queue_logger):
    assert queue is queue_logger.queue
    queue_logger.info(u'some log message')
    assert len(queue.q) == 1
    item = queue.get()
    assert item.msg == 'some log message'
    assert item.level == 'info'


def test_log_args(queue, queue_logger):
    assert queue is queue_logger.queue
    queue_logger.info(u'{!s} {num:d}', 'foo', num=5)
    assert len(queue.q) == 1
    item = queue.get()
    assert item.msg == u'foo 5'


def test_log_args_error(queue, queue_logger):
    assert queue is queue_logger.queue
    queue_logger.info(u'message: {!d} {:d}', 'foo', bar='baz')
    assert len(queue.q) == 1
    item = queue.get()
    assert 'foo' in item.msg
    assert 'bar' in item.msg
    assert 'baz' in item.msg
    assert 'message' in item.msg


def test_logrecord_repr_unpickleable(queue, queue_logger):
    # The items thrown on a multiprocessing queue must be pickleable
    unpickleable = lambda x: x * 2
    with pytest.raises(pickle.PicklingError):
        # Make sure it's not pickleable
        pickle.dumps(unpickleable)

    queue_logger.info(u'Logging unpickleable object: {!r}', unpickleable)
    item = queue.get()
    print pickle.dumps(item)
