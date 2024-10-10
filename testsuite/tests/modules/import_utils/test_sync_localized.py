# encoding: utf-8
"""
Tests for :class:`Cerebrum.modules.import_utils.syncs.NameLanguageSync`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest
import six

from Cerebrum.modules.import_utils import syncs


@pytest.fixture
def person(person_creator):
    person, _ = next(person_creator(1))
    return person


def set_name(person, name_type, nb=None, nn=None, en=None):
    for lang, value in [(person.const.language_nb, nb),
                        (person.const.language_nn, nn),
                        (person.const.language_en, en)]:
        if value:
            person.add_name_with_language(name_variant=int(name_type),
                                          name_language=int(lang),
                                          name=value)


def get_name(person, name_type, name_lang):
    """ Helper to get a given name for a given person. """
    for row in person.search_name_with_language(
            entity_id=person.entity_id,
            name_variant=name_type,
            name_language=name_lang):
        return row['name']
    return None


def test_sync_init(database, const):
    affect = (const.personal_title, const.work_title)
    sync = syncs.NameLanguageSync(database, affect_types=affect)
    assert sync.affect_types == affect


def test_sync_get_type(database, const):
    """ check that sync can look up name types. """
    sync = syncs.NameLanguageSync(database)
    name_type = const.personal_title
    name_strval = six.text_type(name_type)
    name_intval = int(name_type)
    assert sync.get_type(name_strval) is name_type
    assert sync.get_type(name_intval) is name_type


def test_sync_get_subtype(database, const):
    """ check that sync can look up languages. """
    sync = syncs.NameLanguageSync(database)
    lang_type = const.language_en
    lang_strval = six.text_type(lang_type)
    lang_intval = int(lang_type)
    assert sync.get_subtype(lang_strval) is lang_type
    assert sync.get_subtype(lang_intval) is lang_type


def test_sync_add_remove(database, const, person):
    """ check that sync can add and remove values. """
    set_name(person, const.personal_title, en="Assistant", nb="Assistent")
    sync = syncs.NameLanguageSync(database)

    new = [
        (const.work_title, const.language_en, "Rector"),
        (const.work_title, const.language_nb, "Rektor"),
    ]
    added, updated, removed = sync(person, new)

    # Check add/update/remove return value
    assert added == set([
        (const.work_title, const.language_en),
        (const.work_title, const.language_nb),
    ])
    assert updated == set()
    assert removed == set([
        (const.personal_title, const.language_en),
        (const.personal_title, const.language_nb),
    ])

    # Check that our names are set as expected
    assert get_name(person, const.work_title, const.language_en) == "Rector"
    assert get_name(person, const.work_title, const.language_nb) == "Rektor"
    assert not get_name(person, const.personal_title, const.language_nb)
    assert not get_name(person, const.personal_title, const.language_en)


def test_sync_update(database, const, person):
    """ check that sync can update existing values. """
    set_name(person, const.personal_title, en="Assistant", nb="Asst")
    sync = syncs.NameLanguageSync(database)

    new = [
        (const.personal_title, const.language_en, "Assistant"),
        (const.personal_title, const.language_nb, "Assistent"),
    ]
    added, updated, removed = sync(person, new)

    # Check add/update/remove return value
    assert added == set()
    assert updated == set([(const.personal_title, const.language_nb)])
    assert removed == set()

    # Check that our nameesses are set as expected
    new_name = get_name(person, const.personal_title, const.language_nb)
    assert new_name == "Assistent"


def test_sync_no_change(database, const, person):
    """ check that sync does nothing if given existing values. """
    set_name(person, const.personal_title, en="Assistant", nb="Assistent")
    sync = syncs.NameLanguageSync(database)

    new = [
        (const.personal_title, const.language_en, "Assistant"),
        (const.personal_title, const.language_nb, "Assistent"),
    ]
    added, updated, removed = sync(person, new)

    # Check add/update/remove return value
    assert added == set()
    assert updated == set()
    assert removed == set()


def test_sync_affected(database, const, person):
    """ check that affect_types only touches the given name types. """
    set_name(person, const.personal_title, en="Rector")
    set_name(person, const.work_title, nn="Assistent")

    sync = syncs.NameLanguageSync(database, affect_types=(const.work_title,))
    # no nameesses - remove all affected types
    added, updated, removed = sync(person, [])

    assert not added
    assert not updated
    assert removed == set([(const.work_title, const.language_nn)])

    assert get_name(person, const.personal_title, const.language_en)
    assert not get_name(person, const.work_title, const.language_nn)


def test_sync_unaffected(database, const, person):
    """ check that it is an error to set un-affected types. """
    sync = syncs.NameLanguageSync(database, affect_types=(const.work_title,))
    # no nameesses - remove all affected types
    new = [
        (const.personal_title, const.language_en, "Assistant"),
        (const.personal_title, const.language_nb, "Assistent"),
    ]
    with pytest.raises(ValueError) as exc_info:
        sync(person, new)
    error_msg = six.text_type(exc_info.value)
    assert error_msg.startswith("invalid ")


def test_sync_duplicate(database, const, person):
    """ check that it is an error to set two different values. """
    sync = syncs.NameLanguageSync(database)
    new = [
        (const.work_title, const.language_en, "Foo"),
        (const.work_title, const.language_en, "Bar"),
    ]
    with pytest.raises(ValueError) as exc_info:
        sync(person, new)
    error_msg = six.text_type(exc_info.value)
    assert error_msg.startswith("duplicate ")
