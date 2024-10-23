# encoding: utf-8
""" Test fixtures for mod:`Cerebrum.modules.apikeys` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

from Cerebrum import Account
from Cerebrum import Group
from Cerebrum.testutils import datasource


@pytest.fixture(autouse=True)
def _patch_cereconf(cereconf):
    cereconf.AUTH_CRYPT_METHODS = ('plaintext',)


@pytest.fixture
def group_cls():
    return Group.Group


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
def account_cls():
    return Account.Account


@pytest.fixture
def account_creator(database, const, account_cls, initial_account):
    creator_id = initial_account.entity_id
    account_ds = datasource.BasicAccountSource()

    def _create_accounts(owner, limit=1):
        owner_id = owner.entity_id
        owner_type = owner.entity_type

        for account_dict in account_ds(limit=limit):

            account = account_cls(database)
            if owner_type == const.entity_person:
                account_type = None
            else:
                account_type = const.account_program

            account.populate(
                account_dict['account_name'],
                owner_type,
                owner_id,
                account_type,
                creator_id,
                account_dict.get('expire_date'),
            )
            if account_dict.get('password'):
                account.set_password(account_dict.get('password'))
            account.write_db()
            account_dict['entity_id'] = account.entity_id
            yield account, account_dict

    return _create_accounts

