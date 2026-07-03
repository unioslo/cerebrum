# encoding: utf-8
""" Tests for mod:`Cerebrum.modules.apikeys.bofhd_apikey_cmds` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

from Cerebrum.modules.bofhd import bofhd_wofh
from Cerebrum.OU import OU
from Cerebrum.testutils import datasource


@pytest.fixture
def commands(database, logger):
    return bofhd_wofh.BofhdWofhCommands(database, logger)


@pytest.fixture
def ou_cls():
    return OU


@pytest.fixture
def ou_creator(database, ou_cls):
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
def ou(ou_creator):
    ou, _ = next(ou_creator(1))
    return ou


def test_bofhd_wofh_all_group_memberships_account(
        commands, superuser_session, account, group):
    result = commands.wofh_all_group_memberships(
        operator=superuser_session,
        account_name='id:{}'.format(account.entity_id)
    )
    assert len(result) == 0

    group.add_member(account.entity_id)

    result = commands.wofh_all_group_memberships(
        operator=superuser_session,
        account_name='id:{}'.format(account.entity_id)
    )
    assert len(result) == 1

    assert result[0]['entity_id'] == group.entity_id


def test_bofhd_wofh_all_group_memberships_person(
        commands, superuser_session, account, group, person):
    result = commands.wofh_all_group_memberships(
        operator=superuser_session,
        account_name='id:{}'.format(account.entity_id)
    )
    assert len(result) == 0

    account.owner_type = person.entity_type
    account.owner_id = person.entity_id

    group.add_member(account.entity_id)

    result = commands.wofh_all_group_memberships(
        operator=superuser_session,
        account_name='id:{}'.format(account.entity_id)
    )
    assert len(result) == 1

    assert result[0]['entity_id'] == group.entity_id


def test_bofhd_wofh_get_guests(
        commands, account_session, person, ou,constant_module,
        constant_creator):
    result = commands.wofh_get_guests(
        operator=account_session,
    )
    assert result is None

    account_session._owner_id = person.entity_id

    result = commands.wofh_get_guests(
        operator=account_session,
    )
    assert len(result) == 0

    aff_status = constant_creator(
        constant_module._PersonAffStatusCode,
        commands.const.affiliation_ansatt,
        "foo-x-64c28012f1"
    )
    person.add_affiliation(
        ou_id=ou.entity_id,
        affiliation=commands.const.affiliation_ansatt,
        source=commands.const.system_manual,
        status=aff_status,
    )

    # TODO: This test does not work for some reason.
    # It cannot find the OU within the wofh_get_guests method.

    # result = commands.wofh_get_guests(
    #     operator=account_session,
    # )
    # assert len(result) == 0
