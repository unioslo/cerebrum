# -*- coding: utf-8 -*-
""" Tests for `Cerebrum.modules.event_publisher.utils`. """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime

import pytest
import six

import Cerebrum.Account
import Cerebrum.Group
import Cerebrum.Person
from Cerebrum.modules.event_publisher import utils as ep_utils


@pytest.fixture(autouse=True)
def _patch_cereconf(cereconf):
    """ Patched `cereconf` with known ENTITY_TYPE_NAMESPACE mappings. """
    cereconf.ENTITY_TYPE_NAMESPACE = {
        'account': 'account_names',
        'group': 'group_names',
        'host': 'host_names',
    }


@pytest.fixture
def database(database):
    database.cl_init(change_program='test_event_publisher_utils')
    return database


@pytest.fixture
def account(initial_account):
    # we abuse initial_account here to avoid creating a new one
    return initial_account


def test_get_entity_ref_account(cereconf, database, account):
    ref = ep_utils.get_entity_ref(database, account.entity_id)
    assert ref.entity_id == account.entity_id
    assert ref.entity_type == "account"
    assert ref.ident == cereconf.INITIAL_ACCOUNTNAME


@pytest.fixture
def group(database, initial_group):
    # we abuse initial_group here to avoid creating a new one
    return initial_group


def test_get_entity_ref_group(cereconf, database, group):
    ref = ep_utils.get_entity_ref(database, group.entity_id)
    assert ref.entity_id == group.entity_id
    assert ref.entity_type == "group"
    assert ref.ident == cereconf.INITIAL_GROUPNAME


@pytest.fixture
def gender(constant_module):
    """ A new, unique gender constant. """
    code = constant_module._GenderCode
    g = code('bc73da6bb954774d', description='test gender type')
    g.insert()
    return g


@pytest.fixture
def person(database, gender):
    """ Create a basic person entity for tests. """
    pe = Cerebrum.Person.Person(database)
    pe.populate(
        datetime.date(1996, 6, 28),
        gender,
    )
    pe.write_db()
    return pe


def test_get_entity_ref_person(cereconf, database, person):
    ref = ep_utils.get_entity_ref(database, person.entity_id)
    assert ref.entity_id == person.entity_id
    assert ref.entity_type == "person"
    assert ref.ident == six.text_type(person.entity_id)
