# encoding: utf-8
"""
Tests for :mod:`Cerebrum.modules.import_utils.groups`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

from Cerebrum.modules.import_utils import groups as group_sync


# Helpers and fixtures


class _MockGetter(object):
    """ Mock `get_group` factory for GroupMembershipSetter. """

    def __init__(self, value):
        self.value = value

    def __call__(self, database):
        return self.value

    def __repr__(self):
        return "<get_group>"


@pytest.fixture
def group(group_creator):
    group, _ = next(group_creator(limit=1))
    return group


@pytest.fixture
def member(person_creator):
    person, _ = next(person_creator(limit=1))
    return person


@pytest.fixture
def member_sync(group):
    return group_sync.GroupMembershipSetter(_MockGetter(group))


# Tests


def test_member_sync_repr(database, member_sync):
    repr_text = repr(member_sync)
    assert repr_text == "<GroupMembershipSetter <get_group>>"


def test_member_sync_get_group(database, member_sync, group):
    result = member_sync.get_group(database)
    assert result and result.entity_id == group.entity_id


def test_member_sync_add(database, member_sync, group, member):
    did_change = member_sync(database, member.entity_id, True)
    assert did_change
    assert group.has_member(member.entity_id)


def test_member_sync_remove(database, member_sync, group, member):
    group.add_member(member.entity_id)

    did_change = member_sync(database, member.entity_id, False)
    assert did_change
    assert not group.has_member(member.entity_id)


def test_member_sync_already_present(database, member_sync, group, member):
    group.add_member(member.entity_id)

    did_change = member_sync(database, member.entity_id, True)
    assert not did_change
    assert group.has_member(member.entity_id)


def test_member_sync_already_absent(database, member_sync, group, member):
    did_change = member_sync(database, member.entity_id, False)
    assert not did_change
    assert not group.has_member(member.entity_id)
