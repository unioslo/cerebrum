# encoding: utf-8
"""
Tests for :class:`Cerebrum.modules.import_utils.syncs.ExternalIdSync`
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


class _IdHelper(object):

    def __init__(self, source_system):
        self.source = source_system

    def set(self, person, id_type, id_value):
        person._set_external_id(self.source, id_type, id_value)

    def get(self, person, id_type):
        for row in person.get_external_id(source_system=self.source,
                                          id_type=id_type):
            return row['external_id']
        return None


SOURCE_SYSTEM = "sys-1f073188eaba"
ID_TYPE_A = "id-a-c1c885f8d72"
ID_TYPE_B = "id-b-6ff43825c6c"
ID_TYPE_C = "id-c-3946f45e6ec"


@pytest.fixture
def source_system(constant_module, constant_creator):
    return constant_creator(constant_module._AuthoritativeSystemCode,
                            SOURCE_SYSTEM)


@pytest.fixture
def id_type_a(constant_module, constant_creator):
    return constant_creator(
        constant_module._EntityExternalIdCode,
        ID_TYPE_A,
        constant_module.CoreConstants.entity_person,
    )


@pytest.fixture
def id_type_b(constant_module, constant_creator):
    return constant_creator(
        constant_module._EntityExternalIdCode,
        ID_TYPE_B,
        constant_module.CoreConstants.entity_person,
    )


@pytest.fixture
def id_type_c(constant_module, constant_creator):
    return constant_creator(
        constant_module._EntityExternalIdCode,
        ID_TYPE_C,
        constant_module.CoreConstants.entity_person,
    )


@pytest.fixture(autouse=True)
def id_types(source_system, id_type_a, id_type_b, id_type_c):
    helper = _IdHelper(source_system)
    helper.a = id_type_a
    helper.b = id_type_b
    helper.c = id_type_c
    return helper


@pytest.fixture
def person(person_creator):
    person, _ = next(person_creator(1))
    return person


@pytest.fixture
def sync(database, id_types):
    return syncs.ExternalIdSync(database, id_types.source)


#
# Tests
#


def test_sync_init(database, id_types):
    source = id_types.source
    affect = (id_types.a, id_types.b)
    sync = syncs.ExternalIdSync(database, source, affect_types=affect)
    assert sync.source_system == source
    assert sync.affect_types == affect


def test_sync_get_type(sync, id_types):
    """ check that sync can look up id types. """
    id_type = id_types.a
    id_strval = six.text_type(id_type)
    id_intval = int(id_type)
    assert sync.get_type(id_strval) is id_type
    assert sync.get_type(id_intval) is id_type


def test_sync_changes(sync, id_types, person):
    """ check that sync can add, update, and remove values. """
    id_types.set(person, id_types.a, "initial-a")
    id_types.set(person, id_types.c, "initial-c")

    new = [
        (ID_TYPE_A, "updated-a"),  # update
        (ID_TYPE_B, "updated-b"),  # add
        # (ID_TYPE_C, ...),        # remove
    ]
    added, updated, removed = sync(person, new)

    # Check add/update/remove return value
    assert added == set((id_types.b,))
    assert updated == set((id_types.a,))
    assert removed == set((id_types.c,))

    # Check that our ids are set as expected
    assert id_types.get(person, id_types.a) == "updated-a"
    assert id_types.get(person, id_types.b) == "updated-b"
    assert id_types.get(person, id_types.c) is None


def test_sync_no_changes(sync, id_types, person):
    """ check that sync does nothing if given existing values. """
    id_types.set(person, id_types.a, "initial-a")

    new = [(ID_TYPE_A, "initial-a")]
    added, updated, removed = sync(person, new)

    # Check add/update/remove return value
    assert added == set()
    assert updated == set()
    assert removed == set()

    # Check that our ids are set as expected
    assert id_types.get(person, id_types.a) == "initial-a"


def test_sync_affected(database, id_types, person):
    """ check that affect_types only touches the given types. """
    id_types.set(person, id_types.a, "initial-a")
    id_types.set(person, id_types.b, "initial-b")
    id_types.set(person, id_types.c, "initial-c")
    sync = syncs.ExternalIdSync(database, id_types.source,
                                affect_types=(ID_TYPE_C,))

    added, updated, removed = sync(person, [])

    # Check add/update/remove return value
    assert not added
    assert not updated
    assert removed == set((id_types.c,))

    # Check that our names are set as expected
    assert id_types.get(person, id_types.a) == "initial-a"
    assert id_types.get(person, id_types.b) == "initial-b"
    assert id_types.get(person, id_types.c) is None


def test_sync_unaffected(database, id_types, person):
    """ check that it is an error to set un-affected types. """
    sync = syncs.ExternalIdSync(database, id_types.source,
                                affect_types=(ID_TYPE_C,))

    new = [
        (ID_TYPE_A, "updated-a"),  # not in affect_types
        (ID_TYPE_B, "updated-b"),  # not in affect_types
        (ID_TYPE_C, "updated-c"),
    ]
    with pytest.raises(ValueError) as exc_info:
        sync(person, new)
    error_msg = six.text_type(exc_info.value)
    assert error_msg.startswith("invalid ")


def test_sync_duplicate(database, id_types, person):
    """ check that it is an error to set two different values. """
    sync = syncs.ExternalIdSync(database, id_types.source,
                                affect_types=(ID_TYPE_C,))

    new = [
        (ID_TYPE_A, "initial-a"),
        (ID_TYPE_A, "updated-a"),
    ]
    with pytest.raises(ValueError) as exc_info:
        sync(person, new)
    error_msg = six.text_type(exc_info.value)
    assert error_msg.startswith("duplicate ")
