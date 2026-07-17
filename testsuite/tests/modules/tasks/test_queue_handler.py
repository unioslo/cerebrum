# -*- coding: utf-8 -*-
""" Tests for :mod:`Cerebrum.modules.tasks.queue_handler` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

from Cerebrum.modules.tasks import task_queue
from Cerebrum.modules.tasks import task_models
from Cerebrum.modules.tasks import queue_handler
from Cerebrum.utils import date as date_utils


TEST_QUEUE = "test-queue-991a4b02f79fef1b"


class _CallbackRegister(object):

    next_queues = ["callback-1", "callback-2"]

    def __init__(self):
        self.task_list = []

    def get_next_tasks(self, task):
        for sub_queue in self.next_queues:
            yield task_models.Task(task.queue, sub_queue, task.key)

    def __call__(self, db, task):
        self.task_list.append(task)
        return list(self.get_next_tasks(task))


class _TestHandler(queue_handler.QueueHandler):

    queue = TEST_QUEUE
    retry_sub = "retry"


@pytest.fixture
def callback():
    return _CallbackRegister()


@pytest.fixture
def handler(callback):
    return _TestHandler(callback)


@pytest.fixture
def task(database):
    task_queue.sql_push(database, TEST_QUEUE, "", "key-1")
    popped_row = task_queue.sql_pop(database, TEST_QUEUE, "", "key-1")
    return task_models.db_row_to_task(popped_row)


def test_handler_init(handler):
    assert handler


def test_get_retry_task(handler, task):
    error_msg = "test error"
    now = date_utils.now()
    retry_task = handler.get_retry_task(task, error_msg)
    assert retry_task.queue == handler.queue
    assert retry_task.sub == handler.retry_sub
    assert retry_task.key == task.key
    assert retry_task.attempts == task.attempts + 1
    assert retry_task.nbf > now
    assert retry_task.reason.startswith("retry")
    assert error_msg in retry_task.reason


def test_handle_task(database, handler, callback, task):
    assert list(task_queue.sql_search(database, queues=TEST_QUEUE)) == []
    handler.handle_task(database, task)
    assert callback.task_list == [task]
    next_tasks = list(task_queue.sql_search(database, queues=TEST_QUEUE))
    assert len(next_tasks) == 2


def test_get_abandoned_tasks(database, handler):
    queue = handler.queue
    limit = handler.max_attempts
    task_queue.sql_push(database, queue, "", "key-1", attempts=0)
    task_queue.sql_push(database, queue, "", "key-2", attempts=limit - 1)
    task_queue.sql_push(database, queue, "", "key-3", attempts=limit)
    task_queue.sql_push(database, queue, "", "key-4", attempts=limit)
    result = dict(handler.get_abandoned_counts(database))
    assert result == {(queue, ""): 2}
