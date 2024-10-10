# encoding: utf-8
"""
Tests for :mod:`Cerebrum.modules.import_utils.syncs` base classes and helpers

The various sync implementations can be found in their own test modules.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

from Cerebrum.modules.import_utils import syncs


def test_base_sync_init():
    with pytest.raises(TypeError):
        syncs._BaseSync()


def test_kv_sync_init():
    with pytest.raises(TypeError):
        syncs._KeyValueSync()


def test_pretty_const_single(const):
    code = const.entity_person
    expected = "person"
    assert syncs.pretty_const(code) == expected


def test_pretty_const_sequence(const):
    sequence = (
        const.entity_person,
        const.entity_group,
    )
    expected = (
        # sorted result
        "group",
        "person",
    )
    assert syncs.pretty_const(sequence) == expected


def test_pretty_const_pairs(const):
    sequence = (
        (const.entity_person, const.language_en),
        (const.entity_group, const.language_nb),
    )
    expected = (
        # sorted result
        "group/nb",
        "person/en",
    )
    assert syncs.pretty_const_pairs(sequence) == expected
