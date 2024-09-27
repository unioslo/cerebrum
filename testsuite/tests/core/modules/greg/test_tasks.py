# encoding: utf-8
""" Tests for :mod:`Cerebrum.modules.greg.tasks` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
# import datetime

# import pytest

from Cerebrum.modules.greg import tasks
from Cerebrum.modules.tasks import task_models


class MockObj(object):

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


#
# GregImportTasks.create_manual_task tests
#


def test_create_manual_task():
    task = tasks.GregImportTasks.create_manual_task("123")
    expected = task_models.Task(
        queue="greg-person",
        sub="manual",
        key="123",
        attempts=0,
        reason="manually added",
    )
    assert task.to_dict() == expected.to_dict()


#
# GregImportTasks handler
#


def test_handle_task():
    # Because we mock away the import class, we won't actually need a
    # real client.
    mock_client = MockObj()

    # Because our mock importer won't actually use the database, and the greg
    # handler won't create new, delayed tasks on import, we don't actually
    # *need* a real database connection.
    mock_db = MockObj()

    # mock import_class.handle_reference implementation
    handled = []

    def handle_reference(greg_id):
        handled.append(greg_id)

    # mock import_class.__init__ implementation
    def import_factory(db, client=None):
        assert db is mock_db
        assert client is mock_client
        return MockObj(handle_reference=handle_reference)

    handler = tasks.GregImportTasks(mock_client, import_factory)
    task = tasks.GregImportTasks.create_manual_task("123")
    handler.handle_task(mock_db, task)
    assert handled == ["123"]


#
# get_tasks tests
#

class MockEvent(MockObj):

    def __init__(self,
                 content_type="text/plain",
                 content_encoding="utf-8",
                 headers=None,
                 body=""):
        super(MockEvent, self).__init__(
            content_type=content_type,
            content_encoding=content_encoding,
            headers=(headers or {}),
            body=body.encode(content_encoding),
            method=MockObj(
                exchange="ex",
                routing_key="routing.key",
                consumer_tag="tag",
            ),
        )

    def __repr__(self):
        return "<Event>"


def test_get_tasks():
    event = MockEvent(
        body=(
            """
            {
                "id": 100,
                "source": "greg:example:test",
                "type": "person_role.add",
                "data": {
                    "person_id": 1,
                    "role_id": 2
                }
            }
            """
        ),
    )

    results = list(tasks.get_tasks(event))
    assert len(results) == 1
    result = results[0]
    assert result.queue == "greg-person"
    assert not result.sub
    assert result.key == "1"
    assert not result.attempts
    assert result.reason.startswith("event: ")
    assert result.nbf


def test_get_tasks_invalid_message():
    event = MockEvent(body='{"id": 100}')
    results = list(tasks.get_tasks(event))
    assert results == []


def test_get_tasks_no_person_id():
    event = MockEvent(
        body=(
            """
            {
                "id": 100,
                "source": "greg:example:test",
                "type": "person_role.add",
                "data": {"role_id": 2}
            }
            """
        ),
    )

    results = list(tasks.get_tasks(event))
    assert results == []
