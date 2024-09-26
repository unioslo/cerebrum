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

from Cerebrum.modules.tasks import task_models
from Cerebrum.utils import date as date_utils


#
# Payload tests
#

PAYLOAD_DATA = {'foo': "bar"}


@pytest.fixture
def payload():
    return task_models.Payload("example", dict(PAYLOAD_DATA), version=1)


def test_payload_init(payload):
    assert payload.format == "example"
    assert payload.version == 1
    assert payload.data == {'foo': "bar"}


@pytest.mark.parametrize(
    "other",
    [
        task_models.Payload("example", dict(PAYLOAD_DATA), version=1),
        type(str("obj"), (object,), {'format': "example", 'version': 1,
                                     'data': dict(PAYLOAD_DATA)}),
    ],
    ids=["payload", "compatible"],
)
def test_payload_eq(payload, other):
    assert payload == other


@pytest.mark.parametrize(
    "other",
    [
        task_models.Payload("example", dict(PAYLOAD_DATA), version=2),
        type(str("obj"), (object,), {'format': "example", 'version': 1}),
        None,
    ],
    ids=["payload", "non-compatible", "none"],
)
def test_payload_ne(payload, other):
    assert payload != other


def test_payload_to_dict(payload):
    assert payload.to_dict() == {
        'format': "example",
        'version': 1,
        'data': {'foo': "bar"},
    }


def test_payload_from_dict(payload):
    data = payload.to_dict()
    result = task_models.Payload.from_dict(data)
    assert result == payload


#
# Task tests
#


@pytest.fixture
def minimal_task():
    return task_models.Task("queue", "key-123")


def test_task_init_minimal(minimal_task):
    assert minimal_task.queue == "queue"
    assert minimal_task.sub == ""
    assert minimal_task.key == "key-123"
    for attr in ("nbf", "iat", "attempts", "reason", "payload"):
        assert getattr(minimal_task, attr) is None


@pytest.fixture
def task(payload):
    return task_models.Task(
        queue="queue",
        sub="sub-queue",
        key="key-123",
        attempts=3,
        reason="unit test",
        payload=payload,
    )


def test_task_init(task, payload):
    assert task.queue == "queue"
    assert task.sub == "sub-queue"
    assert task.key == "key-123"
    assert task.attempts == 3
    assert task.reason == "unit test"
    assert task.payload == payload
    for attr in ("nbf", "iat"):
        assert getattr(task, attr) is None


def test_task_repr(task):
    repr_text = repr(task)
    # PY3: simplify this, as we don't need to consider u'' vs ''
    assert repr_text.startswith("<Task queue=")
    assert all(key in repr_text for key in ("sub=", "key="))
    assert all(value in repr_text
               for value in ("'queue'", "'sub-queue'", "'key-123'"))


@pytest.mark.parametrize(
    "other",
    [
        task_models.Task("queue", "key-123"),
        type(str("obj"), (object,), {'queue': "queue", 'sub': "",
                                     'key': "key-123", 'iat': None,
                                     'attempts': None, 'nbf': None,
                                     'reason': None, 'payload': None}),
    ],
    ids=["task", "compatible"],
)
def test_task_eq(minimal_task, other):
    assert minimal_task == other


@pytest.mark.parametrize(
    "other",
    [
        task_models.Task("queue", "key-123", reason="non-empty"),
        type(str("obj"), (object,), {'queue': "queue", 'key': "key-123"}),
        None,
    ],
    ids=["task", "non-compatible", "none"],
)
def test_task_ne(minimal_task, other):
    assert minimal_task != other


def test_task_to_dict_minimal(minimal_task):
    assert minimal_task.to_dict() == {
        'queue': "queue",
        'sub': "",
        'key': "key-123",
    }


def test_task_to_dict(task):
    assert task.to_dict() == {
        'queue': "queue",
        'sub': "sub-queue",
        'key': "key-123",
        'attempts': 3,
        'reason': "unit test",
        'payload': task.payload.to_dict(),
    }


def test_task_from_dict_minimal(minimal_task):
    data = minimal_task.to_dict()
    result = task_models.Task.from_dict(data)
    assert result == minimal_task


def test_task_from_dict(task):
    data = task.to_dict()
    result = task_models.Task.from_dict(data)
    assert result == task


#
# db_row_to_task tests
#

def test_db_row_to_task():
    when = date_utils.now()
    row_like = {
        'queue': "foo",
        'sub': "",
        'key': "123",
        'iat': when,
        'nbf': when,
        'attempts': 0,
        'reason': "reason",
        'payload': None,
    }
    task = task_models.db_row_to_task(row_like)
    assert all(getattr(task, k) == row_like[k]
               for k in row_like)


def test_db_row_to_task_empty():
    assert task_models.db_row_to_task({}, allow_empty=True) is None


def test_db_row_to_task_disallow_empty():
    with pytest.raises(Exception):
        task_models.db_row_to_task({})


def test_copy_task(task):
    task_copy = task_models.copy_task(task)
    assert task_copy == task
    assert task_copy is not task
    task_copy.queue = "new-value"
    assert task_copy.queue != task.queue


def test_merge_tasks_with_none(task):
    result = task_models.merge_tasks(task)
    assert result == task


def test_merge_tasks_with_incompatible(task):
    task.nbf = date_utils.now()
    new_task = task_models.copy_task(task)
    new_task.sub = "another-" + task.sub
    with pytest.raises(ValueError):
        task_models.merge_tasks(new_task, task)


def test_merge_tasks_with_older(task):
    new_nbf = date_utils.now()
    old_nbf = new_nbf - datetime.timedelta(hours=1)
    task.nbf = old_nbf
    new_task = task_models.copy_task(task)
    new_task.reason = "new reason"
    new_task.attempts = 10
    new_task.nbf = None
    result = task_models.merge_tasks(new_task, task)
    for attr in sorted(set(new_task.compare_attrs) - set(("nbf", "reason"))):
        assert getattr(result, attr) == getattr(new_task, attr)

    assert result.nbf == task.nbf
    assert result.reason == task.reason


def test_merge_tasks_with_newer(task):
    old_nbf = date_utils.now()
    new_nbf = old_nbf - datetime.timedelta(hours=1)
    task.nbf = old_nbf
    new_task = task_models.copy_task(task)
    new_task.reason = "new reason"
    new_task.attempts = 10
    new_task.nbf = new_nbf
    result = task_models.merge_tasks(new_task, task)
    assert result == new_task


#
# task-id parsing/formatting tests
#


TASK_ID_TESTS = [
    ("foo/bar/baz", ("foo", "bar", "baz")),
    ("foo//baz", ("foo", "", "baz")),
]


@pytest.mark.parametrize(
    "task_id, task_params",
    TASK_ID_TESTS,
    ids=[t[0] for t in TASK_ID_TESTS],
)
def test_parse_task_id_strict(task_id, task_params):
    assert task_models.parse_task_id(task_id) == task_params


@pytest.mark.parametrize(
    "task_id",
    [
        "foo/baz",
        "  /bar/baz",
        "foo/bar/  ",
    ],
)
def test_parse_task_id_strict_error(task_id):
    with pytest.raises(ValueError) as exc_info:
        task_models.parse_task_id(task_id)
    error_msg = six.text_type(exc_info.value)
    assert error_msg.startswith("invalid task-id:")


TASK_ID_DEFAULT_TESTS = [
    ("foo/bar/baz", ("foo", "bar", "baz")),
    ("foo//baz", ("foo", "", "baz")),
    ("foo/baz", ("foo", "default", "baz")),
]


@pytest.mark.parametrize(
    "task_id, task_params",
    TASK_ID_DEFAULT_TESTS,
    ids=[t[0] for t in TASK_ID_DEFAULT_TESTS],
)
def test_parse_task_id_default(task_id, task_params):
    assert task_models.parse_task_id(
        task_id,
        require_sub=False,
        default_sub="default",
    ) == task_params


@pytest.mark.parametrize(
    "task_id",
    [
        "  /bar/baz",
        "foo/bar/  ",
    ],
)
def test_parse_task_id_default_error(task_id):
    with pytest.raises(ValueError) as exc_info:
        task_models.parse_task_id(task_id)
    error_msg = six.text_type(exc_info.value)
    assert error_msg.startswith("invalid task-id:")


TASK_TO_ID_TESTS = [
    # task-like, task_id, queue_id
    (task_models.Task("task", "key", sub="sub"), "task/sub/key", "task/sub"),
    (task_models.Task("task", "key"), "task//key", "task/"),
    ({'queue': "row", 'sub': "sub", 'key': "key"}, "row/sub/key", "row/sub"),
    ({'queue': "row", 'sub': "", 'key': "key"}, "row//key", "row/"),
]


@pytest.mark.parametrize(
    "task_like, task_id",
    [t[0:2] for t in TASK_TO_ID_TESTS],
    ids=[t[1] for t in TASK_TO_ID_TESTS],
)
def test_format_task_id(task_like, task_id):
    assert task_models.format_task_id(task_like) == task_id


@pytest.mark.parametrize(
    "task_like, queue_id",
    [t[0:3:2] for t in TASK_TO_ID_TESTS],
    ids=[t[2] for t in TASK_TO_ID_TESTS],
)
def test_format_queue_id(task_like, queue_id):
    assert task_models.format_queue_id(task_like) == queue_id
