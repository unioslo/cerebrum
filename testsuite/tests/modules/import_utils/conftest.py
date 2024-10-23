# encoding: utf-8
"""
Common fixtures for :mod:`Cerebrum.modules.import_utils` tests
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

import Cerebrum.Group
import Cerebrum.Person
import Cerebrum.OU
from Cerebrum.testutils import datasource


@pytest.fixture
def group_cls():
    return Cerebrum.Group.Group


@pytest.fixture
def group_creator(database, const, group_cls, initial_account):
    """
    A helper fixture to create group objects.
    """
    group_ds = datasource.BasicGroupSource()

    def _create_groups(limit=1):
        for group_dict in group_ds(limit=limit):
            group = group_cls(database)
            group.populate(
                creator_id=initial_account.entity_id,
                visibility=int(const.group_visibility_all),
                name=group_dict['group_name'],
                description=group_dict['description'],
                group_type=int(const.group_type_manual),
            )
            group.expire_date = None
            group.write_db()
            group_dict['entity_id'] = group.entity_id
            yield group, group_dict

    return _create_groups


@pytest.fixture
def ou_cls():
    return Cerebrum.OU.OU


@pytest.fixture
def ou_creator(database, const, ou_cls):
    """
    A helper fixture to create org unit objects.
    """
    ou_ds = datasource.BasicOUSource()

    def _create_org_units(limit=1):
        for ou_dict in ou_ds(limit=limit):
            ou = ou_cls(database)
            ou.populate()
            ou.write_db()
            ou_dict['entity_id'] = ou.entity_id
            yield ou, ou_dict

    return _create_org_units


@pytest.fixture
def person_cls():
    return Cerebrum.Person.Person


@pytest.fixture
def person_creator(database, const, person_cls):
    """
    A helper fixture to create person objects.
    """
    person_ds = datasource.BasicPersonSource()

    def _create_persons(limit=1):
        for person_dict in person_ds(limit=limit):
            person = person_cls(database)
            gender = person_dict.get('gender')
            if gender:
                gender = const.human2constant(gender, const.Gender)
            gender = gender or const.gender_unknown
            person.populate(
                person_dict['birth_date'],
                gender,
                person_dict.get('description'),
            )
            person.write_db()
            person_dict['entity_id'] = person.entity_id
            yield person, person_dict

    return _create_persons
