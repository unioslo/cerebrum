# encoding: utf-8
"""
Tests for :class:`Cerebrum.modules.import_utils.syncs.ContactInfoSync`
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


#
# Constants, helpers, and fixtures
#


SOURCE_SYSTEM = "sys-1f073188eaba"
C_TYPE_A = "a-6c2909d8deb5af"
C_TYPE_B = "b-0dbcdcbed4b8dc"
C_TYPE_C = "c-0e9817f9cc9f11"


@pytest.fixture
def source_system(constant_module, constant_creator):
    return constant_creator(constant_module._AuthoritativeSystemCode,
                            SOURCE_SYSTEM)


@pytest.fixture
def c_type_a(constant_module, constant_creator):
    return constant_creator(constant_module._ContactInfoCode, C_TYPE_A)


@pytest.fixture
def c_type_b(constant_module, constant_creator):
    return constant_creator(constant_module._ContactInfoCode, C_TYPE_B)


@pytest.fixture
def c_type_c(constant_module, constant_creator):
    return constant_creator(constant_module._ContactInfoCode, C_TYPE_C)


class _ContactHelper(object):

    def __init__(self, source_system):
        self.source = source_system

    def set(self, person, contact_type, contact_value):
        person.add_contact_info(self.source, contact_type, contact_value)

    def get(self, person, contact_type):
        for row in person.get_contact_info(source=self.source,
                                           type=contact_type):
            return row['contact_value']
        return None


@pytest.fixture
def contacts(source_system, c_type_a, c_type_b, c_type_c):
    helper = _ContactHelper(source_system)
    helper.a = c_type_a
    helper.b = c_type_b
    helper.c = c_type_c
    return helper


@pytest.fixture
def person(person_creator):
    person, _ = next(person_creator(1))
    return person


@pytest.fixture
def sync(database, source_system):
    return syncs.ContactInfoSync(database, source_system)


#
# Tests
#


def test_sync_init(database, source_system, c_type_a, c_type_b):
    source = source_system
    affect = (c_type_a, c_type_b)
    sync = syncs.ContactInfoSync(database, source, affect_types=affect)
    assert sync.source_system == source
    assert sync.affect_types == affect


def test_sync_get_type(sync, c_type_a):
    """ check that sync can look up contact types. """
    c_type = c_type_a
    c_strval = six.text_type(c_type)
    c_intval = int(c_type)
    assert sync.get_type(c_strval) is c_type
    assert sync.get_type(c_intval) is c_type


def test_sync_changes(sync, contacts, person):
    """ check that sync can add, update, and remove values. """
    contacts.set(person, contacts.a, "initial-a")
    contacts.set(person, contacts.c, "initial-c")
    new = [
        (contacts.a, "updated-a"),  # update
        (contacts.b, "updated-b"),  # add
        # (contacts.c, ...),        # remove
    ]
    added, updated, removed = sync(person, new)

    # Check add/update/remove return value
    assert added == set((contacts.b,))
    assert updated == set((contacts.a,))
    assert removed == set((contacts.c,))

    # Check that our contact values are set as expected
    assert contacts.get(person, contacts.a) == "updated-a"
    assert contacts.get(person, contacts.b) == "updated-b"
    assert contacts.get(person, contacts.c) is None


def test_sync_no_changes(sync, contacts, person):
    """ check that sync does nothing if given existing values. """
    contacts.set(person, contacts.a, "initial-a")
    contacts.set(person, contacts.c, "initial-c")
    new = [
        (contacts.a, "initial-a"),
        (contacts.c, "initial-c"),
    ]
    assert not any(sync(person, new))
    assert contacts.get(person, contacts.a) == "initial-a"
    assert contacts.get(person, contacts.b) is None
    assert contacts.get(person, contacts.c) == "initial-c"


def test_sync_affected(database, contacts, person):
    """ check that affect_types only touches the given types. """
    contacts.set(person, contacts.a, "initial-a")
    contacts.set(person, contacts.b, "initial-b")
    contacts.set(person, contacts.c, "initial-c")
    affect_types = (contacts.c,)
    sync = syncs.ContactInfoSync(database, contacts.source,
                                 affect_types=affect_types)

    added, updated, removed = sync(person, [])
    assert not added
    assert not updated
    assert removed == set(affect_types)
    assert contacts.get(person, contacts.a) == "initial-a"
    assert contacts.get(person, contacts.b) == "initial-b"
    assert contacts.get(person, contacts.c) is None


def test_sync_unaffected(database, contacts, person):
    """ check that it is an error to set un-affected types. """
    sync = syncs.ContactInfoSync(database, contacts.source,
                                 affect_types=(contacts.c,))
    new = [
        (contacts.a, "updated-a"),
        (contacts.b, "updated-b"),
        (contacts.c, "updated-c"),
    ]
    with pytest.raises(ValueError) as exc_info:
        sync(person, new)
    error_msg = six.text_type(exc_info.value)
    assert error_msg.startswith("invalid ")


def test_sync_duplicate(sync, contacts, person):
    """ check that it is an error to set two different values. """
    new = [
        (contacts.a, "initial-a"),
        (contacts.a, "updated-a"),
    ]
    with pytest.raises(ValueError) as exc_info:
        sync(person, new)
    error_msg = six.text_type(exc_info.value)
    assert error_msg.startswith("duplicate ")
