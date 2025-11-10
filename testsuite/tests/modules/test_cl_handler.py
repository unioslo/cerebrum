# encoding: utf-8
"""
Unit tests for :mod:`Cerebrum.modules.CLHandler`.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

import Cerebrum.Person
from Cerebrum import DatabaseAccessor
from Cerebrum.modules import CLHandler
from Cerebrum.modules import ChangeLog
from Cerebrum.testutils import datasource


CHANGE_KEY = "test-a5b007fc03beca"


#
# CLHandler helper function tests
#


@pytest.mark.parametrize(
    "value",
    ["x", "Foo_123.Baz", "Foo-5678901234567890", CHANGE_KEY],
)
def test_valid_change_keys(value):
    assert CLHandler.validate_change_key(value) == value


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("", id="empty"),
        pytest.param("Foo|Bar", id="invalid-character"),
        pytest.param("Foo-56789012345678901", id="too-long"),
    ],
)
def test_valid_change_keys_invalid(value):
    with pytest.raises(ValueError):
        CLHandler.validate_change_key(value)


def test_add_ranges_for_key(database):
    first_id, last_id = (0, 99)
    inserted_row = CLHandler.add_range_for_key(database, CHANGE_KEY,
                                               first_id, last_id)
    assert dict(inserted_row) == {
        'evthdlr_key': CHANGE_KEY,
        'first_id': first_id,
        'last_id': last_id,
    }
    ranges = list(CLHandler.get_ranges_for_key(database, CHANGE_KEY))
    assert (first_id, last_id) in ranges


INITIAL_RANGES = [(4, 99), (200, 299), (400, 449)]


@pytest.fixture
def ranges(database):
    """ a fixture that adds INITIAL_RANGES to the changelog handler tables. """
    for first, last in reversed(INITIAL_RANGES):
        CLHandler.add_range_for_key(database, CHANGE_KEY, first, last)
    return INITIAL_RANGES


def test_get_ranges_for_key(database, ranges):
    results = CLHandler.get_ranges_for_key(database, CHANGE_KEY)
    assert list(results) == ranges


def test_clear_ranges_for_key(database, ranges):
    results = CLHandler.clear_ranges_for_key(database, CHANGE_KEY)
    assert len(results) == len(ranges)
    assert list(CLHandler.get_ranges_for_key(database, CHANGE_KEY)) == []


@pytest.mark.parametrize(
    "ranges, limits",
    [
        pytest.param(
            [(0, 99), (200, 299)],
            [(100, 199), (300, None)],
            id="zero-start",
        ),
        pytest.param(
            [(-1, 99), (200, 299)],
            [(100, 199), (300, None)],
            id="negative-start",
        ),
        pytest.param(
            [(50, 99), (200, 299)],
            [(0, 49), (100, 199), (300, None)],
            id="positive-start",
        ),
        pytest.param(
            [(0, 59), (60, 69), (80, 89)],
            [(70, 79), (90, None)],
            id="continuous",
        ),
        pytest.param(
            [(0, 19), (50, 65), (60, 69), (80, 89)],
            [(20, 49), (70, 79), (90, None)],
            id="overlap",
        ),
        pytest.param(
            [],
            [(0, None)],
            id="empty",
        ),
    ],
)
def test_ranges_to_limits(ranges, limits):
    result = CLHandler._ranges_to_limits(ranges)
    assert list(result) == limits


#
# CLHandler.CLHandler tests
#


class _NoCommitMixin(DatabaseAccessor.DatabaseAccessor):
    """ Prevent `DatabaseAccessor.commit()` from ending our transaction. """

    def commit(self):
        pass


class _SimpleChangeLog(_NoCommitMixin, ChangeLog.ChangeLog):
    pass


@pytest.fixture
def changelog(database):
    cl = _SimpleChangeLog(database)
    cl.cl_init(change_program=__name__)
    return cl


class _NoCommitHandler(_NoCommitMixin, CLHandler.CLHandler):
    pass


@pytest.fixture
def changelog_handler(database):
    return _NoCommitHandler(database)


@pytest.fixture
def person_cls():
    return Cerebrum.Person.Person


@pytest.fixture
def person_creator(database, const, person_cls):
    """
    A helper fixture to create person objects.
    """
    person_ds = datasource.BasicPersonSource()

    def _create_persons(limit=1):
        for person_dict in person_ds(limit=limit):
            person = person_cls(database)
            gender = person_dict.get('gender')
            if gender:
                gender = const.human2constant(gender, const.Gender)
            gender = gender or const.gender_unknown
            person.populate(
                person_dict['birth_date'],
                gender,
                person_dict.get('description'),
            )
            person.write_db()
            person_dict['entity_id'] = person.entity_id
            yield person, person_dict

    return _create_persons


@pytest.fixture
def person(person_creator):
    person, _ = next(person_creator(1))
    return person


@pytest.fixture
def changelog_records(database, clconst, changelog, person):
    # We claim that all change_ids before now has been processed
    last_id = changelog.get_last_changelog_id()
    CLHandler.add_range_for_key(database, CHANGE_KEY, -1, last_id)

    # Make some fake changelog records
    records = [
        {
            'subject_entity': person.entity_id,
            'change_type_id': clconst.person_create,
            'destination_entity': None,
            'change_params': {
                'name': "Foo Bar",
            },
        },
        {
            'subject_entity': person.entity_id,
            'change_type_id': clconst.person_update,
            'destination_entity': None,
            'change_params': {
                'dob': "1999-01-01",
            },
        },
    ]

    for kwargs in records:
        changelog.log_change(**kwargs)
    changelog.write_log()
    return records


def test_handler_get_events(database, clconst, changelog_handler,
                            changelog_records):
    events = changelog_handler.get_events(CHANGE_KEY, None)
    assert len(events) == len(changelog_records)

    # We should get the events back in the same order we added them
    for added, fetched in zip(changelog_records, events):
        assert added['subject_entity'] == fetched['subject_entity']
        assert int(added['change_type_id']) == int(fetched['change_type_id'])


def test_handler_commit_confirmations(database, clconst, changelog,
                                      changelog_handler, changelog_records):
    # In our setup, we *should* have a single, continuous range of "handled"
    # change ids, which ends before our two "fake" events.
    # If we only confirm the last of the two events, we should end up with two
    # separate ranges.  Let's test that this works as expected.
    #
    events = changelog_handler.get_events(CHANGE_KEY, None)

    # Sanity check our events
    last_id = changelog.get_last_changelog_id()
    assert [e['change_id'] for e in events] == [last_id - 1, last_id]

    # Confirm the last event - we've stubbed out the actual
    # `changelog_handler.commit()`
    changelog_handler.confirm_event(events[-1])
    changelog_handler.commit_confirmations()

    # We should now have a "hole" in our ranges that omits (last_id - 1):
    results = list(CLHandler.get_ranges_for_key(database, CHANGE_KEY))
    assert results == [(-1, last_id - 2), (last_id, last_id)]

    # Let's double check by getting our events again - we should only get the
    # unconfirmed event:
    events = changelog_handler.get_events(CHANGE_KEY, None)
    assert len(events) == 1
    assert events[0]['change_id'] == last_id - 1
