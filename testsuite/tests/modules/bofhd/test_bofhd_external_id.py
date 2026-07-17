# encoding: utf-8
""" Tests for mod:`Cerebrum.modules.apikeys.bofhd_apikey_cmds` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

from Cerebrum.modules.bofhd import bofhd_external_id
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied


@pytest.fixture
def auth(database):
    return bofhd_external_id.BofhdExtidAuth(database)


@pytest.fixture
def commands(database, logger):
    return bofhd_external_id.BofhdExtidCommands(database, logger)


@pytest.fixture
def target_entity(person):
    return person


def test_bofhd_can_get_extid(
        auth, account, target_entity, grant_op):
    # Check access to own account info
    assert auth.can_get_extid(
        account.entity_id,
        entity=account,
        id_type="NO_BIRTHNO",
    )

    with pytest.raises(PermissionDenied):
        assert auth.can_get_extid(
            account.entity_id,
            entity=target_entity,
            id_type="NO_BIRTHNO",
        )
    grant_op(
        account,
        auth.const.auth_view_external_id,
        target_entity,
        auth.const.auth_target_type_global_person,
    )
    assert auth.can_get_extid(
        account.entity_id,
        entity=account,
        id_type="NO_BIRTHNO",
    )


def test_bofhd_can_set_extid(
        auth, superuser_session, account, target_entity, grant_op):
    # Only superusers can do this, there is no op-code for it
    with pytest.raises(PermissionDenied):
        assert auth.can_set_extid(
            account.entity_id,
            entity=account,
            id_type="NO_BIRTHNO",
            source_system=str(auth.const.system_manual),
        )

    assert auth.can_set_extid(
        superuser_session.get_entity_id(),
        entity=account,
        id_type="NO_BIRTHNO",
        source_system=str(auth.const.system_manual),
    )


def test_bofhd_can_clear_extid(
        auth, superuser_session, account, target_entity, grant_op):
    # Only superusers can do this, there is no op-code for it
    with pytest.raises(PermissionDenied):
        assert auth.can_clear_extid(
            account.entity_id,
            entity=account,
            id_type="NO_BIRTHNO",
            source_system=str(auth.const.system_manual),
        )

    assert auth.can_clear_extid(
        superuser_session.get_entity_id(),
        entity=account,
        id_type="NO_BIRTHNO",
        source_system=str(auth.const.system_manual),
    )


def test_bofhd_can_list_extid(
        auth, account, target_entity, grant_op):
    # Pretty much anyone can list external id types
    assert auth.can_list_extid(
        account.entity_id,
        entity=account,
    )

    assert auth.can_list_extid(
        account.entity_id,
        entity=target_entity,
    )


testdata = [
    ("FS", "NO_BIRTHNO", "01019012345"),
]


@pytest.mark.parametrize("id_source,id_type,id_value", testdata)
def test_bofhd_extid_set(
    commands, superuser_session, person, id_source, id_type, id_value):

    result = commands.entity_extid_set(
        operator=superuser_session,
        entity_target="id:{}".format(person.entity_id),
        _id_source=id_source,
        _id_type=id_type,
        _id_value=id_value,
    )
    assert result == {
        'id_source': id_source,
        'id_type': id_type,
        'id_value': id_value,
        'entity_type': 'person',
        'entity_id': person.entity_id
    }
    assert len(person.get_external_id()) == 1
    external_id = person.get_external_id()[0]
    assert external_id['external_id'] == id_value


@pytest.mark.parametrize("id_source,id_type,id_value", testdata)
def test_bofhd_extid_set_error(
    commands, superuser_session, person, id_source, id_type, id_value):

    with pytest.raises(CerebrumError) as exception:
        commands.entity_extid_set(
            operator=superuser_session,
            entity_target="id:{}".format(person.entity_id),
            _id_source="INVALID",
            _id_type=id_type,
            _id_value=id_value,
        )
    assert "invalid source system" in str(exception.value).lower()

    with pytest.raises(CerebrumError) as exception:
        commands.entity_extid_set(
            operator=superuser_session,
            entity_target="id:{}".format(person.entity_id),
            _id_source=id_source,
            _id_type="INVALID",
            _id_value=id_value,
        )
    assert "invalid id type" in str(exception.value).lower()

    with pytest.raises(CerebrumError) as exception:
        commands.entity_extid_set(
            operator=superuser_session,
            entity_target="id:{}".format("-1"),
            _id_source=id_source,
            _id_type=id_type,
            _id_value=id_value,
        )
    assert "no such entity" in str(exception.value).lower()


@pytest.mark.parametrize("id_source,id_type,id_value", testdata)
def test_bofhd_extid_get(
    commands, superuser_session, person, id_source, id_type, id_value):

    commands.entity_extid_set(
        operator=superuser_session,
        entity_target="id:{}".format(person.entity_id),
        _id_source=id_source,
        _id_type=id_type,
        _id_value=id_value,
    )
    assert len(person.get_external_id()) == 1
    result = commands.entity_extid_get(
        operator=superuser_session,
        entity_target="id:{}".format(person.entity_id),
        _id_source=id_source,
        _id_type=id_type,
    )
    assert len(result) == 1
    assert result[0] == {
        'entity_id': person.entity_id,
        'entity_type': 'person',
        'id_type': id_type,
        'id_source': id_source,
        'id_value': id_value,
    }


@pytest.mark.parametrize("id_source,id_type,id_value", testdata)
def test_bofhd_extid_search(
    commands, superuser_session, person, id_source, id_type, id_value):

    commands.entity_extid_set(
        operator=superuser_session,
        entity_target="id:{}".format(person.entity_id),
        _id_source=id_source,
        _id_type=id_type,
        _id_value=id_value,
    )
    assert len(person.get_external_id()) == 1
    result = commands.entity_extid_search(
        operator=superuser_session,
        id_pattern=id_value,
        _id_source=id_source,
        _id_type=id_type,
    )
    assert len(result) == 1
    assert result[0] == {
        'entity_id': person.entity_id,
        'entity_type': 'person',
        'id_type': id_type,
        'id_source': id_source,
        'id_value': id_value,
    }


@pytest.mark.parametrize("id_source,id_type,id_value", testdata)
def test_bofhd_extid_list(
    commands, superuser_session, person, id_source, id_type, id_value):

    commands.entity_extid_set(
        operator=superuser_session,
        entity_target="id:{}".format(person.entity_id),
        _id_source=id_source,
        _id_type=id_type,
        _id_value=id_value,
    )
    assert len(person.get_external_id()) == 1
    result = commands.entity_extid_list(
        operator=superuser_session,
        entity_target="id:{}".format(person.entity_id),
    )
    assert len(result) == 1
    assert result[0] == {
        'entity_id': person.entity_id,
        'entity_type': 'person',
        'id_type': id_type,
        'id_source': id_source,
    }


@pytest.mark.parametrize("id_source,id_type,id_value", testdata)
def test_bofhd_extid_clear(
    commands, superuser_session, person, id_source, id_type, id_value):

    commands.entity_extid_set(
        operator=superuser_session,
        entity_target="id:{}".format(person.entity_id),
        _id_source=id_source,
        _id_type=id_type,
        _id_value=id_value,
    )
    assert len(person.get_external_id()) == 1
    result = commands.entity_extid_clear(
        operator=superuser_session,
        entity_target="id:{}".format(person.entity_id),
        _id_source=id_source,
        _id_type=id_type
    )
    assert result == {
        'entity_id': person.entity_id,
        'entity_type': 'person',
        'id_type': id_type,
        'id_source': id_source,
    }
    assert len(person.get_external_id()) == 0
