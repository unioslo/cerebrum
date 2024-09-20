# -*- coding: utf-8 -*-
""" Tests for :mod:`Cerebrum.modules.tasks.task_models` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime

import pytest
import six

import Cerebrum.Errors
from Cerebrum.modules.tasks import task_queue
from Cerebrum.utils import date as date_utils


TEST_QUEUE = "test-queue-991a4b02f79fef1b"


#
# push tests
#


def test_push(database):
    result = task_queue.sql_push(database, TEST_QUEUE, "sub", "key",
                                 reason="test-push")
    assert result['queue'] == TEST_QUEUE
    assert result['sub'] == "sub"
    assert result['key'] == "key"
    assert result['iat']
    assert result['nbf']
    assert result['attempts'] == 0
    assert result['reason'] == "test-push"
    assert not result['payload']


def test_push_noop(database):
    task_queue.sql_push(database, TEST_QUEUE, "sub", "key",
                        reason="foo")
    noop = task_queue.sql_push(database, TEST_QUEUE, "sub", "key",
                               reason="foo")
    assert noop is None


def test_push_payload(database):
    payload = {'foo': "bar"}
    result = task_queue.sql_push(database, TEST_QUEUE, "sub", "key",
                                 payload=payload)
    assert result['payload'] == payload


def test_push_update_some(database):
    original = dict(task_queue.sql_push(database, TEST_QUEUE, "sub", "key"))
    result = dict(task_queue.sql_push(database, TEST_QUEUE, "sub", "key",
                                      reason="test-reason"))
    assert result.pop('reason') == "test-reason"
    original.pop('reason')
    assert result == original


def test_push_update_all(database):
    new_iat = date_utils.now()
    new_nbf = date_utils.now() + datetime.timedelta(hours=1)
    new_payload = {'foo': 1, 'bar': "foo"}
    task_queue.sql_push(database, TEST_QUEUE, "sub", "key")
    result = dict(task_queue.sql_push(database, TEST_QUEUE, "sub", "key",
                                      iat=new_iat,
                                      nbf=new_nbf,
                                      reason="test-reason",
                                      attempts=3,
                                      payload=new_payload))
    assert result['iat'] == new_iat
    assert result['nbf'] == new_nbf
    assert result['reason'] == "test-reason"
    assert result['attempts'] == 3
    assert result['payload'] == new_payload


def test_push_clear_payload(database):
    original = task_queue.sql_push(database, TEST_QUEUE, "sub", "key",
                                   payload={'foo': 1})
    assert original['payload']
    result = task_queue.sql_push(database, TEST_QUEUE, "sub", "key",
                                 payload=None)
    assert result['payload'] is None


#
# get/pop tests
#


def test_get(database):
    pushed = task_queue.sql_push(database, TEST_QUEUE, "sub", "key")
    result = task_queue.sql_get(database, TEST_QUEUE, "sub", "key")
    assert dict(result) == dict(pushed)


def test_get_missing(database):
    with pytest.raises(Cerebrum.Errors.NotFoundError) as exc_info:
        task_queue.sql_get(database, TEST_QUEUE, "sub", "key")

    error_msg = six.text_type(exc_info.value)
    assert TEST_QUEUE + "/sub/key" in error_msg


def test_pop(database):
    pushed = task_queue.sql_push(database, TEST_QUEUE, "sub", "key")
    popped = task_queue.sql_pop(database, TEST_QUEUE, "sub", "key")
    assert dict(popped) == dict(pushed)
    with pytest.raises(Cerebrum.Errors.NotFoundError):
        # check that the task is removed
        task_queue.sql_get(database, TEST_QUEUE, "sub", "key")


def test_pop_missing(database):
    with pytest.raises(Cerebrum.Errors.NotFoundError) as exc_info:
        task_queue.sql_pop(database, TEST_QUEUE, "sub", "key")

    error_msg = six.text_type(exc_info.value)
    assert TEST_QUEUE + "/sub/key" in error_msg


#
# search tests
#


def test_search_empty(database):
    assert list(task_queue.sql_search(database, queues=TEST_QUEUE)) == []


def test_search_queue(database):
    task_queue.sql_push(database, TEST_QUEUE, "", "1")
    task_queue.sql_push(database, TEST_QUEUE, "", "2")
    task_queue.sql_push(database, TEST_QUEUE, "sub", "3")
    results = list(task_queue.sql_search(database, queues=TEST_QUEUE, subs=""))
    assert len(results) == 2


def test_search_queue_limit(database):
    task_queue.sql_push(database, TEST_QUEUE, "", "1")
    task_queue.sql_push(database, TEST_QUEUE, "", "2")
    task_queue.sql_push(database, TEST_QUEUE, "", "3")
    results = list(task_queue.sql_search(database, queues=TEST_QUEUE, limit=2))
    assert len(results) == 2


def test_search_queue_order(database):
    t = datetime.date.today()
    d = datetime.timedelta
    task_queue.sql_push(database, TEST_QUEUE, "", "1", nbf=(t - d(days=1)))
    task_queue.sql_push(database, TEST_QUEUE, "", "2", nbf=(t - d(days=3)))
    task_queue.sql_push(database, TEST_QUEUE, "", "3", nbf=(t - d(days=2)))
    results = list(task_queue.sql_search(database, queues=TEST_QUEUE))
    assert len(results) == 3
    key_order = [r['key'] for r in results]
    assert key_order == ["2", "3", "1"]


def test_search_iat(database):
    t = datetime.date.today()
    d = datetime.timedelta
    task_queue.sql_push(database, TEST_QUEUE, "", "1", iat=(t - d(days=1)))
    task_queue.sql_push(database, TEST_QUEUE, "", "2", iat=(t - d(days=3)))
    task_queue.sql_push(database, TEST_QUEUE, "", "3", iat=(t - d(days=5)))
    results = list(task_queue.sql_search(database, queues=TEST_QUEUE,
                                         iat_after=(t - d(days=4)),
                                         iat_before=(t - d(days=2))))
    assert len(results) == 1
    assert results[0]['key'] == "2"


def test_search_iat_invalid(database):
    t = datetime.date.today()
    d = datetime.timedelta
    with pytest.raises(ValueError) as exc_info:
        task_queue.sql_search(database,
                              iat_after=(t - d(days=2)),
                              iat_before=(t - d(days=4)))

    error_msg = six.text_type(exc_info.value)
    assert "iat_after: cannot be after iat_before" in error_msg


def test_search_nbf(database):
    t = datetime.date.today()
    d = datetime.timedelta
    task_queue.sql_push(database, TEST_QUEUE, "", "1", nbf=(t - d(days=1)))
    task_queue.sql_push(database, TEST_QUEUE, "", "2", nbf=(t - d(days=3)))
    task_queue.sql_push(database, TEST_QUEUE, "", "3", nbf=(t - d(days=5)))
    results = list(task_queue.sql_search(database, queues=TEST_QUEUE,
                                         nbf_after=(t - d(days=4)),
                                         nbf_before=(t - d(days=2))))
    assert len(results) == 1
    assert results[0]['key'] == "2"


def test_search_nbf_invalid(database):
    t = datetime.date.today()
    d = datetime.timedelta
    with pytest.raises(ValueError) as exc_info:
        task_queue.sql_search(database,
                              nbf_after=(t - d(days=2)),
                              nbf_before=(t - d(days=4)))

    error_msg = six.text_type(exc_info.value)
    assert "nbf_after: cannot be after nbf_before" in error_msg


def test_search_min_attempts(database):
    task_queue.sql_push(database, TEST_QUEUE, "", "1", attempts=1)
    task_queue.sql_push(database, TEST_QUEUE, "", "2", attempts=2)
    task_queue.sql_push(database, TEST_QUEUE, "", "3", attempts=3)
    result_keys = set(
        r['key']
        for r in task_queue.sql_search(database, queues=TEST_QUEUE,
                                       min_attempts=2))
    assert result_keys == set(("2", "3"))


def test_search_max_attempts(database):
    task_queue.sql_push(database, TEST_QUEUE, "", "1", attempts=1)
    task_queue.sql_push(database, TEST_QUEUE, "", "2", attempts=2)
    task_queue.sql_push(database, TEST_QUEUE, "", "3", attempts=3)
    result_keys = set(
        r['key']
        for r in task_queue.sql_search(database, queues=TEST_QUEUE,
                                       max_attempts=3))
    assert result_keys == set(("1", "2"))


def test_search_attempts_invalid(database):
    with pytest.raises(ValueError) as exc_info:
        task_queue.sql_search(database, queues=TEST_QUEUE,
                              min_attempts=4, max_attempts=3)

    error_msg = six.text_type(exc_info.value)
    assert "max_attempts: cannot be less than min_attempts" in error_msg


#
# delete tests
#


def test_delete_empty(database):
    assert list(task_queue.sql_delete(database, queues=TEST_QUEUE)) == []


def test_delete_queue(database):
    task_queue.sql_push(database, TEST_QUEUE, "", "1")
    task_queue.sql_push(database, TEST_QUEUE, "", "2")
    task_queue.sql_push(database, TEST_QUEUE, "sub", "3")
    deleted_keys = [
        r['key']
        for r in task_queue.sql_delete(database, queues=TEST_QUEUE, subs="")]
    assert len(deleted_keys) == 2
    assert set(deleted_keys) == set(("1", "2"))
    remaining_keys = [
        r['key']
        for r in task_queue.sql_search(database, queues=TEST_QUEUE)]
    assert set(remaining_keys) == set(("3",))


def test_delete_queue_limit(database):
    t = datetime.date.today()
    d = datetime.timedelta
    task_queue.sql_push(database, TEST_QUEUE, "", "1", nbf=(t - d(days=1)))
    task_queue.sql_push(database, TEST_QUEUE, "", "2", nbf=(t - d(days=3)))
    task_queue.sql_push(database, TEST_QUEUE, "", "3", nbf=(t - d(days=2)))
    deleted_keys = [
        r['key']
        for r in task_queue.sql_delete(database, queues=TEST_QUEUE, limit=2)]
    assert len(deleted_keys) == 2
    assert set(deleted_keys) == set(("2", "3"))
    remaining_keys = [
        r['key']
        for r in task_queue.sql_search(database, queues=TEST_QUEUE)]
    assert len(remaining_keys) == 1
    assert set(remaining_keys) == set(("1",))


#
# pop_next tests
#

def test_pop_next(database):
    t = datetime.date.today()
    d = datetime.timedelta
    task_queue.sql_push(database, TEST_QUEUE, "", "1", nbf=(t - d(days=1)))
    task_queue.sql_push(database, TEST_QUEUE, "", "2", nbf=(t - d(days=3)))
    task_queue.sql_push(database, TEST_QUEUE, "", "3", nbf=(t - d(days=2)))

    next_task = task_queue.sql_pop_next(database, queues=TEST_QUEUE)
    # oldest matching nbf
    assert next_task['key'] == "2"


def test_pop_next_missing(database):
    task_queue.sql_push(database, TEST_QUEUE, "", "1")
    task_queue.sql_push(database, TEST_QUEUE, "", "2")
    task_queue.sql_push(database, TEST_QUEUE, "", "3")
    with pytest.raises(Cerebrum.Errors.NotFoundError):
        task_queue.sql_pop_next(database, queues=TEST_QUEUE, subs="sub-queue")


#
# test queue counts
#


ANOTHER_TEST_QUEUE = "test-queue-d18fdeacff05bb2a"


def test_queue_counts(database):
    task_queue.sql_push(database, TEST_QUEUE, "", "1")
    task_queue.sql_push(database, TEST_QUEUE, "sub-queue", "2")
    task_queue.sql_push(database, ANOTHER_TEST_QUEUE, "", "3")
    task_queue.sql_push(database, TEST_QUEUE, "", "4")

    args = {'queues': (TEST_QUEUE, ANOTHER_TEST_QUEUE)}
    result = {}
    for queue, count in task_queue.sql_get_queue_counts(database, **args):
        result[queue] = count

    assert result == {
        TEST_QUEUE: 3,
        ANOTHER_TEST_QUEUE: 1,
    }


def test_subqueue_counts(database):
    task_queue.sql_push(database, TEST_QUEUE, "", "1")
    task_queue.sql_push(database, TEST_QUEUE, "sub-queue", "2")
    task_queue.sql_push(database, ANOTHER_TEST_QUEUE, "", "3")
    task_queue.sql_push(database, TEST_QUEUE, "", "4")

    args = {'queues': (TEST_QUEUE, ANOTHER_TEST_QUEUE)}
    result = {}
    for queue, sub, count in task_queue.sql_get_subqueue_counts(database,
                                                                **args):
        result[(queue, sub)] = count

    assert result == {
        (TEST_QUEUE, ""): 2,
        (TEST_QUEUE, "sub-queue"): 1,
        (ANOTHER_TEST_QUEUE, ""): 1,
    }
