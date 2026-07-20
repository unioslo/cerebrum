# -*- coding: utf-8 -*-
"""
Tests for :mod:`Cerebrum.modules.entity_note.note_mixins`

"""

from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import pytest
import six

from Cerebrum.modules.entity_note import note_db


@pytest.fixture
def note():
    return {
        'subject': 'test',
        'description': 'test description',
    }


def test_add_note(person, account, note):
    """Test adding a note to a person entity."""

    note_id = person.add_note(account.entity_id, **note)

    assert note_id is not None

    notes = person.get_notes()
    assert len(notes) == 1
    assert notes[0]["note_id"] == note_id
    assert notes[0]["subject"] == note["subject"]
    assert notes[0]["description"] == note["description"]
    assert notes[0]["creator_id"] == account.entity_id
    assert notes[0]["entity_id"] == person.entity_id


def test_add_note_long_subject(person, account):
    with pytest.raises(ValueError) as exc_info:
        long_subject = "A" * 80
        person.add_note(account.entity_id, subject=long_subject, description="test")
    error_msg = six.text_type(exc_info.value)
    assert "Subject must not be null "
    "and must be no longer than 70 characters." in error_msg


def test_get_empty_note(person):
    notes = person.get_notes()
    assert len(notes) == 0


def test_delete_note(person, account, note):
    note_id = person.add_note(account.entity_id, **note)
    notes = person.get_notes()
    assert len(notes) == 1
    person.delete_note(note_id)
    assert len(person.get_notes()) == 0


def test_delete_not_existing_note(person):
    person.delete_note(12345)
    assert len(person.get_notes()) == 0


def test_delete_note_wrong_entity(person_creator, account, note):
    person1, _ = next(person_creator(1))
    person2, _ = next(person_creator(1))
    note_id = person1.add_note(account.entity_id, **note)
    assert len(person1.get_notes()) == 1
    person2.delete_note(note_id)
    assert len(person1.get_notes()) == 1
    assert len(person2.get_notes()) == 0


def test_delete_entity_with_notes(person, account, note):
    person.add_note(account.entity_id, **note)
    person.add_note(account.entity_id, **note)
    assert len(person.get_notes()) == 2
    p_id = person.entity_id
    person.delete()
    remaining = list(note_db.sql_search_notes(person._db, entity_id=p_id))
    assert len(remaining) == 0
