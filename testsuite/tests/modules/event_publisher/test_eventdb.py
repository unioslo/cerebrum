# encoding: utf-8
"""
Unit tests for :mod:`Cerebrum.modules.event_publisher.eventdb`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import json

import pytest

import Cerebrum.Errors
from Cerebrum.modules.event_publisher import event
from Cerebrum.modules.event_publisher import eventdb


# TODO: This test module is a bit minimal.  We should test more combinations of
# input arguments, and should probably verify e.g. returned dates a bit better.
# We also need tests for:
#
# - `EventsAccessor.get_uprocessed`
# - `EventsAccessor.release_all`
#
# ... but those won't work as well with an existing, populated database.  They
# require a bit more test setup, and tests will run slow on a database with a
# lot of events.


@pytest.fixture
def accessor(database):
    """ an initialized EventsAccessor. """
    return eventdb.EventsAccessor(database)


# EventType for test events
EVENT_TYPE = "example"


@pytest.fixture(autouse=True, scope="module")
def event_type():
    """ ensure our EVENT_TYPE is defined. """
    # Note: We really only need this to be a *real* EventType object
    # for our `eventdb.from_row` tests.
    return event.EventType(EVENT_TYPE, "example event type for tests")


# A (non-existing) subject entity.  We don't bother referring to a real entity,
# as the EventsAccessor doesn't really need it to exist.
SUBJECT = {
    'subject_id': 1,
    'subject_type': "example",
    'subject_ident': "foo",
}


@pytest.fixture
def event_data():
    """ Some event data for our example event(s). """
    # TODO: certain values have special meaning in `eventdb.from_row` - we
    # should test these specifically
    return {'foo': "bar"}


@pytest.fixture
def event_data_text(event_data):
    """ our event_data fixture as a json string. """
    return json.dumps(event_data)


def _create_fixture_event(accessor, event_data=None):
    return accessor.create_event(
        event_type=EVENT_TYPE,
        data=event_data,
        **SUBJECT)


@pytest.fixture
def event_id(accessor, event_data):
    """ the event-id of our fixture data in the database. """
    return _create_fixture_event(accessor, event_data)


def test_create_event(accessor):
    event_id = _create_fixture_event(accessor)
    assert event_id > 0


def test_get_event(accessor, event_id, event_data_text):
    row = accessor.get_event(event_id)

    # mandatory values
    assert row['event_id'] == event_id
    assert row['event_type'] == EVENT_TYPE
    assert row['subject_id'] == SUBJECT['subject_id']
    assert row['subject_type'] == SUBJECT['subject_type']
    assert row['subject_ident'] == SUBJECT['subject_ident']

    # optional, empty values
    assert row['event_data'] == event_data_text
    assert row['schedule'] is None

    # auto-columns
    assert row['failed'] == 0
    assert row['taken_time'] is None
    assert row['timestamp']


def test_get_event_missing(accessor):
    with pytest.raises(Cerebrum.Errors.NotFoundError):
        # there can never be an event with a nevative event-id
        accessor.get_event(-1)


def test_delete_event(accessor, event_id):
    deleted_id = accessor.delete_event(event_id)
    assert deleted_id == event_id

    with pytest.raises(Cerebrum.Errors.NotFoundError):
        accessor.get_event(deleted_id)


def test_delete_event_missing(accessor):
    with pytest.raises(Cerebrum.Errors.NotFoundError):
        # there can never be an event with a nevative event-id
        accessor.delete_event(-1)


def test_fail_count_inc(accessor, event_id):
    before = accessor.get_event(event_id)
    accessor.fail_count_inc(event_id)
    after = accessor.get_event(event_id)
    assert after['failed'] == before['failed'] + 1


def test_fail_count_reset(accessor, event_id):
    accessor.fail_count_inc(event_id)
    accessor.fail_count_inc(event_id)
    before = accessor.get_event(event_id)
    # sanity check the setup of our event
    assert before['failed'] > 0

    # the test:
    reset_id = accessor.fail_count_reset(event_id)
    assert reset_id == event_id
    curr = accessor.get_event(event_id)
    assert curr['failed'] == 0


def test_lock_event(accessor, event_id):
    accessor.lock_event(event_id)
    row = accessor.get_event(event_id)
    assert row['taken_time'] is not None


def test_lock_locked_event(accessor, event_id):
    accessor.lock_event(event_id)

    with pytest.raises(Cerebrum.Errors.NotFoundError):
        accessor.lock_event(event_id)


def test_release_event(accessor, event_id):
    accessor.lock_event(event_id)
    accessor.release_event(event_id)
    row = accessor.get_event(event_id)
    assert row['taken_time'] is None


def test_release_unlocked_event(accessor, event_id):
    accessor.release_event(event_id)
    row = accessor.get_event(event_id)
    assert row['taken_time'] is None


def test_row_to_event(accessor, event_id, event_data):
    row = accessor.get_event(event_id)
    obj = eventdb.from_row(row)

    assert obj.event_type == event.EventType(EVENT_TYPE)
    assert obj.subject == event.EntityRef(SUBJECT['subject_id'],
                                          SUBJECT['subject_type'],
                                          SUBJECT['subject_ident'])

    # TODO: We should test de-serializing data from event_data into these
    #       attributes.
    assert obj.attributes == set()
    assert obj.context == set()
    assert obj.objects == set()

    assert obj.scheduled is None
    assert obj.timestamp is not None
