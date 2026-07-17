# encoding: utf-8
"""
Tests for :class:`Cerebrum.modules.import_utils.syncs.PersonNameSync`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest
import six

from Cerebrum import Errors
from Cerebrum.modules.import_utils import syncs


#
# Constants, helpers, and fixtures
#


SOURCE_SYSTEM = "sys-1f073188eaba"


@pytest.fixture
def source_system(constant_module, constant_creator):
    return constant_creator(constant_module._AuthoritativeSystemCode,
                            SOURCE_SYSTEM)


class _NameHelper(object):

    def __init__(self, source_system):
        self.source = source_system

    def set(self, person, first=None, last=None, full=None):
        const = person.const
        person.affect_names(self.source,
                            const.name_first, const.name_last, const.name_full)
        for name_type, name_value in [(const.name_first, first),
                                      (const.name_last, last),
                                      (const.name_full, full)]:
            if not name_value:
                continue
            person.populate_name(name_type, name_value)
        person.write_db()

    def get(self, person, name_type):
        try:
            return person.get_name(source_system=self.source,
                                   variant=name_type)
        except Errors.NotFoundError:
            return None


@pytest.fixture
def names(source_system):
    return _NameHelper(source_system)


@pytest.fixture
def sync(database, source_system):
    return syncs.PersonNameSync(database, source_system)


@pytest.fixture
def person(person_creator):
    person, _ = next(person_creator(1))
    return person


#
# Tests
#


def test_sync_init(database, const, source_system):
    source = source_system
    affect = (const.name_first, const.name_last)
    sync = syncs.PersonNameSync(database, source, affect_types=affect)
    assert sync.source_system == source
    assert sync.affect_types == affect


def test_sync_get_type(sync, const):
    name_type = const.name_first
    name_strval = six.text_type(name_type)
    name_intval = int(name_type)
    assert sync.get_type(name_strval) is name_type
    assert sync.get_type(name_intval) is name_type


def test_sync_changes(sync, const, names, person):
    """ check that sync can add, update, and remove values. """
    names.set(person, first="John", full="J. Smith")

    new = [
        (const.name_first, "Jane"),  # update
        (const.name_last, "Smith"),  # add
        # (const.name_full, ...),    # remove
    ]
    added, updated, removed = sync(person, new)

    assert added == set((const.name_last,))
    assert updated == set((const.name_first,))
    assert removed == set((const.name_full,))

    assert names.get(person, const.name_first) == "Jane"
    assert names.get(person, const.name_last) == "Smith"
    assert names.get(person, const.name_full) is None


def test_sync_no_changes(sync, const, names, person):
    """ check that sync does nothing if given existing values. """
    names.set(person, first="John", last="Smith")
    new = [
        (const.name_first, "John"),
        (const.name_last, "Smith"),
    ]
    added, updated, removed = sync(person, new)
    assert not any(sync(person, new))
    assert names.get(person, const.name_first) == "John"
    assert names.get(person, const.name_last) == "Smith"
    assert names.get(person, const.name_full) is None


def test_sync_affected(database, const, names, person):
    """ check that affect_types only touches the given types. """
    names.set(person, first="John", last="Smith", full="J. Smith")
    sync = syncs.PersonNameSync(database, names.source,
                                affect_types=(const.name_full,))

    # no names - remove all affected types
    added, updated, removed = sync(person, [])

    assert not added
    assert not updated
    assert removed == set((const.name_full,))

    # Check that unaffected names are still set
    assert names.get(person, const.name_first) == "John"
    assert names.get(person, const.name_last) == "Smith"
    assert names.get(person, const.name_full) is None


def test_sync_unaffected(database, const, names, person):
    """ check that it is an error to set un-affected types. """
    sync = syncs.PersonNameSync(database, names.source,
                                affect_types=(const.name_full,))
    new = [
        (const.name_first, "Foo"),  # not in affect_types
        (const.name_last, "Bar"),   # not in affect_types
        (const.name_full, "Foo Bar"),
    ]
    with pytest.raises(ValueError) as exc_info:
        sync(person, new)
    error_msg = six.text_type(exc_info.value)
    assert error_msg.startswith("invalid ")


def test_sync_duplicate(sync, const, person):
    """ check that it is an error to set two different values. """
    new = [
        (const.name_first, "Foo"),
        (const.name_first, "Bar"),
    ]
    with pytest.raises(ValueError) as exc_info:
        sync(person, new)
    error_msg = six.text_type(exc_info.value)
    assert error_msg.startswith("duplicate ")
