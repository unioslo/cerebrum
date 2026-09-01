# encoding: utf-8
"""
Common fixtures for :mod:`Cerebrum.modules.entity_note` tests
"""

from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

import Cerebrum.Account
import Cerebrum.Group
import Cerebrum.Person
import Cerebrum.OU
from Cerebrum.testutils import datasource


@pytest.fixture
def person_cls():
    """Get the Person class to use for creating test persons."""
    return Cerebrum.Person.Person


@pytest.fixture
def account_cls():
    return Cerebrum.Account.Account


@pytest.fixture
def group_cls():
    return Cerebrum.Group.Group


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


@pytest.fixture
def account_creator(database, const, account_cls, person_creator):
    """
    A helper fixture to create account objects.

    Accounts are needed as note creators (creator_id).
    """
    account_ds = datasource.BasicAccountSource()

    def _create_accounts(limit=1):
        for account_dict in account_ds(limit):
            # Create a person to own the account
            person, person_dict = next(person_creator(1))

            # Create the account
            account = account_cls(database)
            acc_name = account_dict['account_name']
            account.populate(
                name=acc_name,
                owner_type=const.entity_person,
                owner_id=person.entity_id,
                np_type=None,
                creator_id=2,
                expire_date=None,
            )
            account.write_db()

            account_dict = {
                'entity_id': account.entity_id,
                'account_name': acc_name,
                'owner_id': person.entity_id,
                'person': person,
                'person_dict': person_dict,
            }
            yield account, account_dict

    return _create_accounts


@pytest.fixture
def group_creator(database, group_cls, const):
    """
    A helper fixture to create group objects.

    Useful for testing notes on different entity types.
    """
    group_ds = datasource.BasicGroupSource()

    def _create_groups(limit=1):
        for group_dict in group_ds(limit):
            group = group_cls(database)
            group_name = group_dict['group_name']
            group.populate(
                creator_id=2,
                visibility=const.group_visibility_all,
                name=group_name,
                description="Test group",
                group_type=const.group_type_internal,
            )
            group.write_db()

            group_dict = {
                'entity_id': group.entity_id,
                'group_name': group_name,
            }
            yield group, group_dict

    return _create_groups


@pytest.fixture
def person(person_creator):
    person, _ = next(person_creator(1))
    return person


@pytest.fixture
def account(account_creator):
    account, _ = next(account_creator(1))
    return account


@pytest.fixture
def group(group_creator):
    group, _ = next(group_creator(1))
    return group
