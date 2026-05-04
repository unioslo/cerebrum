# encoding: utf-8
"""
Tests for the fs consent group in `Cerebrum.modules.fs`.

NOTE: These tests depend on a proper FS_GROUP_NAME and FS_GROUP_DESC being set
in `cereconf`.  This value is set by `Cereconf.default_config`, and should
generally not be overridden.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime
import logging

import pytest

import Cerebrum.Person
from Cerebrum.modules.fs import fs_group
from Cerebrum.modules.fs import import_fs
from Cerebrum.testutils.log_utils import StrictNullHandler


@pytest.fixture(autouse=True, scope="module")
def _patch_logging():
    """ catch badly formatted log records in dbal.logger. """
    logger = logging.getLogger("test_consent_group")
    logger.addHandler(StrictNullHandler())
    logger.setLevel(-100)
    fs_group.logger = logger
    import_fs.logger = logger


@pytest.fixture
def person_cls():
    return Cerebrum.Person.Person


@pytest.fixture
def person(const, database, person_cls):
    person = person_cls(database)
    person.populate(
        datetime.date(2020, 1, 1),
        const.gender_unknown,
    )
    person.write_db()
    return person


def test_get_group(cereconf, database):
    """ test getting the fs consent group. """
    # This is using the `Cerebrum.group.template` functionality, so we don't
    # need extensive tests here - we just need to make sure that
    # `get_fs_consent_group` exists, and returns a group.
    consent_group = fs_group.get_fs_consent_group(database)
    assert consent_group.group_name == cereconf.FS_GROUP_NAME


@pytest.fixture
def consent_group(database):
    return fs_group.get_fs_consent_group(database)


def test_consent_group_manager_init(database):
    update_consent = import_fs.ConsentGroupManager(database)
    assert update_consent
    assert update_consent.group


@pytest.fixture
def update_consent(database):
    return import_fs.ConsentGroupManager(database)


def test_set_consent(update_consent, consent_group, person):
    update_consent.set_consent(person.entity_id)
    assert consent_group.has_member(person.entity_id)


def test_revoke_consent(update_consent, consent_group, person):
    update_consent.set_consent(person.entity_id)
    update_consent.revoke_consent(person.entity_id)
    assert not consent_group.has_member(person.entity_id)
