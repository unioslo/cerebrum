# encoding: utf-8
""" Tests for mod:`Cerebrum.modules.apikeys.bofhd_apikey_cmds` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

from Cerebrum.modules.bofhd import bofhd_contact_info
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied


@pytest.fixture
def auth(database):
    return bofhd_contact_info.BofhdContactAuth(database)


@pytest.fixture
def commands(database, logger):
    return bofhd_contact_info.BofhdContactCommands(database, logger)


@pytest.fixture
def target_entity(account_2):
    return account_2


@pytest.mark.parametrize("target_type", [
    'auth_target_type_host',
    'auth_target_type_disk',
    'auth_target_type_ou',
])
def test_bofhd_can_get_contact_info(
        auth, account, target_entity, grant_op, target_type):
    # Check access to own account info
    assert auth.can_get_contact_info(
        account.entity_id,
        entity=account,
        contact_type="MOBILE",
    )

    with pytest.raises(PermissionDenied):
        auth.can_get_contact_info(
            account.entity_id,
            entity=target_entity,
            contact_type="MOBILE",
        )
    grant_op(
        account,
        auth.const.auth_view_contactinfo,
        target_entity,
        getattr(auth.const, target_type)
    )
    assert auth.can_get_contact_info(
        account.entity_id,
        entity=target_entity,
        contact_type="MOBILE",
    )


@pytest.mark.parametrize("target_type", [
    'auth_target_type_host',
    'auth_target_type_disk',
    'auth_target_type_ou',
])
def test_bofhd_can_add_contact_info(
        auth, account, target_entity, grant_op, target_type):
    # Account cannot edit their own contact info by default
    with pytest.raises(PermissionDenied):
        auth.can_add_contact_info(
            account.entity_id,
            entity=account,
            contact_type="MOBILE",
            source_system=str(auth.const.system_manual),
        )

    with pytest.raises(PermissionDenied):
        auth.can_add_contact_info(
            account.entity_id,
            entity=target_entity,
            contact_type="MOBILE",
            source_system=str(auth.const.system_manual),
        )
    grant_op(
        account,
        auth.const.auth_add_contactinfo,
        target_entity,
        getattr(auth.const, target_type)
    )
    assert auth.can_add_contact_info(
        account.entity_id,
        entity=target_entity,
        contact_type="MOBILE",
        source_system=str(auth.const.system_manual),
    )


@pytest.mark.parametrize("target_type", [
    'auth_target_type_host',
    'auth_target_type_disk',
    'auth_target_type_ou',
])
def test_bofhd_can_remove_contact_info(
        auth, account, target_entity, grant_op, target_type):
    # Account cannot edit their own contact info by default
    with pytest.raises(PermissionDenied):
        auth.can_remove_contact_info(
            account.entity_id,
            entity=account,
            contact_type="MOBILE",
            source_system=str(auth.const.system_manual),
        )

    with pytest.raises(PermissionDenied):
        auth.can_remove_contact_info(
            account.entity_id,
            entity=target_entity,
            contact_type="MOBILE",
            source_system=str(auth.const.system_manual),
        )
    grant_op(
        account,
        auth.const.auth_remove_contactinfo,
        target_entity,
        getattr(auth.const, target_type)
    )
    assert auth.can_remove_contact_info(
        account.entity_id,
        entity=target_entity,
        contact_type="MOBILE",
        source_system=str(auth.const.system_manual),
    )


testdata = [
    ("EMAIL", "ola.nordmann@uio.no"),
    ("PHONE", "+4712345678"),
    ("MOBILE", "+4712345678"),
    ("PRIVATEMOBILE", "12345678"),
]


@pytest.mark.parametrize("contact_type,contact_value", testdata)
def test_bofhd_contact_info_add(
    commands, superuser_session, account, contact_type, contact_value):

    result = commands.entity_contactinfo_add(
        operator=superuser_session,
        entity_target="id:{}".format(account.entity_id),
        contact_type=contact_type,
        contact_value=contact_value,
    )
    assert result == {
        'source_system': str(commands.const.system_manual),
        'contact_type': contact_type,
        'contact_value': contact_value,
        'entity_type': 'account',
        'entity_id': account.entity_id
    }
    assert len(account.get_contact_info()) == 1
    contact_info = account.get_contact_info()[0]
    assert contact_info['entity_id'] == account.entity_id
    assert contact_info['contact_value'] == contact_value


def test_bofhd_contact_info_add_error(commands, superuser_session, account):
    with pytest.raises(CerebrumError) as exception:
        commands.entity_contactinfo_add(
            operator=superuser_session,
            entity_target="id:{}".format(account.entity_id),
            contact_type="MOBILE",
            contact_value="+47abcdefgh",
        )
    assert "only contain digits" in str(exception.value)
    assert len(account.get_contact_info()) == 0

    with pytest.raises(CerebrumError) as exception:
        commands.entity_contactinfo_add(
            operator=superuser_session,
            entity_target="id:{}".format(account.entity_id),
            contact_type="INVALID",
            contact_value="+4712345678",
        )
    assert "contact type" in str(exception.value)
    assert len(account.get_contact_info()) == 0


@pytest.mark.parametrize("contact_type,contact_value", testdata)
def test_bofhd_contact_info_remove(
    commands, superuser_session, account, contact_type, contact_value):

    commands.entity_contactinfo_add(
        operator=superuser_session,
        entity_target="id:{}".format(account.entity_id),
        contact_type=contact_type,
        contact_value=contact_value,
    )
    assert len(account.get_contact_info()) == 1
    result = commands.entity_contactinfo_remove(
        operator=superuser_session,
        entity_target="id:{}".format(account.entity_id),
        source_system=str(commands.const.system_manual),
        contact_type=contact_type,
    )
    assert result == {
        'source_system': str(commands.const.system_manual),
        'contact_type': contact_type,
        'contact_value': contact_value,
        'entity_type': 'account',
        'entity_id': account.entity_id
    }
    assert len(account.get_contact_info()) == 0


@pytest.mark.parametrize("contact_type,contact_value", testdata)
def test_bofhd_contact_info_show(
    commands, superuser_session, account, contact_type, contact_value):

    with pytest.raises(CerebrumError) as exception:
        commands.entity_contactinfo_show(
            operator=superuser_session,
            entity_target="id:{}".format(account.entity_id),
        )
    assert "no contact info" in str(exception.value).lower()
    commands.entity_contactinfo_add(
        operator=superuser_session,
        entity_target="id:{}".format(account.entity_id),
        contact_type=contact_type,
        contact_value=contact_value,
    )
    assert len(account.get_contact_info()) == 1
    result = commands.entity_contactinfo_show(
        operator=superuser_session,
        entity_target="id:{}".format(account.entity_id),
    )
    assert len(result) == 1
    contact_info = result[0]
    assert contact_info['entity_id'] == account.entity_id
    assert contact_info['source_system'] == str(commands.const.system_manual)
    assert contact_info['contact_type'] == contact_type
    assert contact_info['contact_value'] == contact_value


@pytest.mark.parametrize("contact_type,contact_value", testdata)
def test_bofhd_contact_info_search(
    commands, superuser_session, account, contact_type, contact_value):

    commands.entity_contactinfo_add(
        operator=superuser_session,
        entity_target="id:{}".format(account.entity_id),
        contact_type=contact_type,
        contact_value=contact_value,
    )
    assert len(account.get_contact_info()) == 1
    result = commands.entity_contactinfo_search(
        operator=superuser_session,
        contact_value=contact_value,
    )
    assert len(result) == 1
    contact_info = result[0]
    assert contact_info['entity_id'] == account.entity_id
    assert contact_info['source_system'] == str(commands.const.system_manual)
    assert contact_info['contact_type'] == contact_type
    assert contact_info['contact_value'] == contact_value
