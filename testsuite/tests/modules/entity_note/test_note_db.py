# encoding: utf-8
"""
Common fixtures for :mod:`Cerebrum.modules.entity_note` tests
"""

from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import pytest
import datetime
from Cerebrum.modules.entity_note import note_db


@pytest.fixture
def note_data_person(person, account):
    return {
        'entity_id': person.entity_id,
        'creator_id': account.entity_id,
        'subject': 'test',
        'description': 'test description',
    }


@pytest.fixture
def note():
    return {
        'subject': 'test',
        'description': 'test description',
    }

#
# sql_add_note tests
#


def test_sql_add_note(database, note_data_person):
    result = note_db.sql_add_note(database, **note_data_person)
    assert result["entity_id"] == note_data_person["entity_id"]
    assert result["creator_id"] == note_data_person["creator_id"]
    assert result["subject"] == note_data_person["subject"]
    assert result["description"] == note_data_person["description"]
    assert result["note_id"] is not None
    assert result["create_date"] is not None


def test_sql_add_note_to_group(database, group, account, note):
    new_note = note_db.sql_add_note(
        database,
        entity_id=group.entity_id,
        creator_id=account.entity_id,
        **note
    )
    note_id = new_note['note_id']
    found_note = list(note_db.sql_search_notes(database, note_id=note_id))
    assert len(found_note) == 1
    assert found_note[0] == new_note


#
# sql_search_note tests
#


def test_sql_search_note_by_id(database, note_data_person):
    new_note = note_db.sql_add_note(database, **note_data_person)
    results = list(
        note_db.sql_search_notes(database, note_id=new_note['note_id']))
    assert len(results) == 1


def test_search_empty(database, note_data_person):
    assert (
        list(
            note_db.sql_search_notes(database,
                                     entity_id=note_data_person["entity_id"])
        )
        == []
    )


def test_search_notes_limit(database, note_data_person):
    note_db.sql_add_note(database, **note_data_person)
    note_db.sql_add_note(database, **note_data_person)
    note_db.sql_add_note(database, **note_data_person)
    results = list(note_db.sql_search_notes(database, limit=2))
    assert len(results) == 2


def test_search_target_id(database, note_data_person):
    note_db.sql_add_note(database, **note_data_person)
    note_db.sql_add_note(database, **note_data_person)
    results = list(
        note_db.sql_search_notes(database,
                                 entity_id=note_data_person["entity_id"])
    )
    assert len(results) == 2


def test_search_notes_invalid_date_range(database, person):
    t = datetime.datetime.now()
    d = datetime.timedelta
    with pytest.raises(ValueError) as exc_info:
        list(
            note_db.sql_search_notes(
                database,
                entity_id=person.entity_id,
                created_after=(t - d(days=2)),
                created_before=(t - d(days=4)),
            )
        )
    assert "invalid range" in str(exc_info.value)


#
# sql_delete_note tests
#


def test_delete_note(database, note_data_person):
    entity_id = note_data_person['entity_id']
    note_db.sql_add_note(database, **note_data_person)
    note2 = note_db.sql_add_note(database, **note_data_person)
    delete_id = note2['note_id']

    remaining_before = list(
        note_db.sql_search_notes(database, entity_id=entity_id))
    assert len(remaining_before) == 2

    deleted_notes = list(
        note_db.sql_delete_notes(database, note_id=note2["note_id"]))
    assert len(deleted_notes) == 1
    assert deleted_notes[0]['note_id'] == delete_id

    remaining_after = list(
        note_db.sql_search_notes(database, entity_id=entity_id))
    assert len(remaining_after) == 1


def test_delete_note_when_nothing_matches(database, note_data_person):
    entity_id = note_data_person['entity_id']
    note_db.sql_add_note(database, **note_data_person)

    # A negative entity-id can't exist, so this shouldn't delete any notes
    deleted = list(note_db.sql_delete_notes(database, entity_id=-1))
    assert len(deleted) == 0

    # Check that we didn't just delete all notes, and that the sql_delete_notes
    # return value is bad or something
    remaining = list(note_db.sql_delete_notes(database, entity_id=entity_id))
    assert len(remaining) == 1


def test_delete_notes(database, note_data_person):
    entity_id = note_data_person['entity_id']
    note_db.sql_add_note(database, **note_data_person)
    note_db.sql_add_note(database, **note_data_person)

    deleted = list(note_db.sql_delete_notes(database, entity_id=entity_id))
    assert len(deleted) == 2

    remaining = list(note_db.sql_search_notes(database, entity_id=entity_id))
    assert len(remaining) == 0


#
# Check that _prefix can't leak through to our _select()
#


def test_search_invalid_arg(database, person):
    with pytest.raises(TypeError):
        note_db.sql_search_notes(database,
                                 entity_id=person.entity_id,
                                 prefix="foo")


def test_delete_invalid_arg(database, person):
    with pytest.raises(TypeError):
        note_db.sql_delete_notes(database,
                                 entity_id=person.entity_id,
                                 _prefix="foo")
