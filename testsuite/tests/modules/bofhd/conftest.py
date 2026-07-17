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
from Cerebrum import Person
from Cerebrum.testutils import datasource
from Cerebrum.group.template import GroupTemplate
from Cerebrum.modules.bofhd import session
from Cerebrum.modules.bofhd.auth import BofhdAuthOpSet, BofhdAuthOpTarget, BofhdAuthRole


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
def group(group_creator):
    group, _ = next(group_creator(1))
    return group


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


@pytest.fixture
def superuser_group(database, cereconf):
    tpl = GroupTemplate(
        group_name=cereconf.BOFHD_SUPERUSER_GROUP,
        group_description="bofhd-superusers",
        group_type="internal-group",
        group_visibility="A",
        conflict=GroupTemplate.CONFLICT_IGNORE,
    )
    return tpl(database)


@pytest.fixture
def superuser(database, account_creator, superuser_group):
    owner = superuser_group
    account, _ = next(account_creator(owner, 1))
    superuser_group.add_member(account.entity_id)
    return account


@pytest.fixture
def superuser_session(database, superuser):
    operator = session.BofhdSession(database)
    operator.set_authenticated_entity(superuser.entity_id, "127.0.0.1")
    return operator


@pytest.fixture
def account(database, account_creator, superuser_group):
    owner = superuser_group
    account, _ = next(account_creator(owner, 1))
    return account


@pytest.fixture
def account_2(database, account_creator, superuser_group):
    owner = superuser_group
    account, _ = next(account_creator(owner, 1))
    return account


@pytest.fixture
def account_session(database, account):
    operator = session.BofhdSession(database)
    operator.set_authenticated_entity(account.entity_id, "127.0.0.1")
    return operator


@pytest.fixture
def person_cls():
    return Person.Person


@pytest.fixture
def person_creator(database, const, person_cls):
    person_ds = datasource.BasicPersonSource()

    def _create_persons(limit=1):
        for person_dict in person_ds(limit=limit):
            person = person_cls(database)
            gender = person_dict.get('gender')
            if gender:
                gender = const.human2constant(gender, const.Gender)
            gender = gender or const.gender_unknown

            person.populate(person_dict['birth_date'],
                            gender,
                            person_dict.get('description'))
            person.write_db()
            person_dict['entity_id'] = person.entity_id
            yield person, person_dict

    return _create_persons


@pytest.fixture
def person(person_creator):
    person, _ = next(person_creator(limit=1))
    return person


@pytest.fixture
def auth_role(database):
    return BofhdAuthRole(database)


@pytest.fixture
def grant_op(auth_role, database):
    def _grant_op(operator, op_code, target, target_type):
        op_set = BofhdAuthOpSet(database)
        op_set.populate("foo-127598749")
        op_set.write_db()
        op_set.add_operation(op_code)
        op_target = BofhdAuthOpTarget(database)
        op_target.populate(target.entity_id, target_type)
        op_target.write_db()
        auth_role.grant_auth(
            operator.entity_id,
            op_set.op_set_id,
            op_target.op_target_id
        )
    return _grant_op
