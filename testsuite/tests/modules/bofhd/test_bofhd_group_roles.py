# encoding: utf-8
""" Tests for mod:`Cerebrum.modules.apikeys.bofhd_apikey_cmds` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest
import six

from Cerebrum.modules.bofhd import bofhd_group_roles
from Cerebrum.group.GroupRoles import GroupRoles
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied


@pytest.fixture
def auth(database):
    return bofhd_group_roles.BofhdGroupRoleAuth(database)


@pytest.fixture
def commands(database, logger):
    return bofhd_group_roles.BofhdGroupRoleCommands(database, logger)


@pytest.fixture
def target_group(group_creator):
    group, _ = next(group_creator(1))
    return group


def test_bofhd_can_add_group_admin(
        auth, account, target_group, grant_op):
    with pytest.raises(PermissionDenied):
        assert not auth.can_add_group_admin(
            account.entity_id,
            group=target_group,
        )
    grant_op(
        account,
        auth.const.auth_add_group_admin,
        target_group,
        auth.const.auth_target_type_group,
    )
    assert auth.can_add_group_admin(
        account.entity_id,
        group=target_group,
    )


def test_bofhd_can_remove_group_admin(
        auth, account, target_group, grant_op):
    # Uses the same permission as add_group_admin
    with pytest.raises(PermissionDenied):
        assert not auth.can_remove_group_admin(
            account.entity_id,
            group=target_group,
        )
    grant_op(
        account,
        auth.const.auth_add_group_admin,
        target_group,
        auth.const.auth_target_type_group,
    )
    assert auth.can_remove_group_admin(
        account.entity_id,
        group=target_group,
    )


def test_bofhd_can_add_group_moderator(
        auth, account, target_group, grant_op):
    # Uses the same permission as add_group_admin
    with pytest.raises(PermissionDenied):
        assert not auth.can_add_group_moderator(
            account.entity_id,
            group=target_group,
        )
    grant_op(
        account,
        auth.const.auth_add_group_admin,
        target_group,
        auth.const.auth_target_type_group,
    )
    assert auth.can_add_group_moderator(
        account.entity_id,
        group=target_group,
    )


def test_bofhd_can_remove_group_moderator(
        auth, account, target_group, grant_op):
    # Uses the same permission as add_group_admin
    with pytest.raises(PermissionDenied):
        assert not auth.can_remove_group_moderator(
            account.entity_id,
            group=target_group,
        )
    grant_op(
        account,
        auth.const.auth_add_group_admin,
        target_group,
        auth.const.auth_target_type_group,
    )
    assert auth.can_remove_group_moderator(
        account.entity_id,
        group=target_group,
    )


def test_bofhd_can_list_group_roles(
        auth, account, target_group):
    # Anyone can do this
    assert auth.can_list_group_roles(
        account.entity_id,
    )

    assert auth.can_list_group_roles(
        account.entity_id,
    )


def test_bofhd_can_list_group_owners(
        auth, account, target_group):
    # Anyone can do this
    assert auth.can_list_group_owners(
        account.entity_id,
        group=target_group,
    )

    assert auth.can_list_group_owners(
        account.entity_id,
        group=target_group,
    )


def test_bofhd_group_add_admin(
        commands, superuser_session, group, target_group):

    assert not GroupRoles.is_admin(
        GroupRoles(group._db), target_group.entity_id, group.entity_id
    )

    result = commands.group_add_admin(
        operator=superuser_session,
        lookup="{}".format(target_group.entity_id),
        dest_group="{}".format(group.entity_id),
    )

    assert result['group_id'] == group.entity_id
    assert result['admin_id'] == target_group.entity_id
    assert result['group_type'] == 'manual-group'
    assert result['admin_type'] == 'group'

    assert GroupRoles.is_admin(
        GroupRoles(group._db), target_group.entity_id, group.entity_id
    )


def test_bofhd_group_remove_admin(
        commands, superuser_session, group, target_group):
    test_bofhd_group_add_admin(commands, superuser_session, group, target_group)

    result = commands.group_remove_admin(
        operator=superuser_session,
        lookup="{}".format(target_group.entity_id),
        dest_group="{}".format(group.entity_id),
    )

    assert result['group_id'] == group.entity_id
    assert result['admin_id'] == target_group.entity_id
    assert result['group_type'] == 'manual-group'
    assert result['admin_type'] == 'group'

    assert not GroupRoles.is_admin(
        GroupRoles(group._db), target_group.entity_id, group.entity_id
    )

def test_bofhd_group_add_moderator(
        commands, superuser_session, group, target_group):
    assert not GroupRoles.is_moderator(
        GroupRoles(group._db), target_group.entity_id, group.entity_id
    )

    result = commands.group_add_moderator(
        operator=superuser_session,
        lookup="{}".format(target_group.entity_id),
        dest_group="{}".format(group.entity_id),
    )

    assert result['group_id'] == group.entity_id
    assert result['moderator_id'] == target_group.entity_id
    assert result['group_type'] == 'manual-group'
    assert result['moderator_type'] == 'group'

    assert GroupRoles.is_moderator(
        GroupRoles(group._db), target_group.entity_id, group.entity_id
    )


def test_bofhd_group_remove_moderator(
        commands, superuser_session, group, target_group):
    test_bofhd_group_add_moderator(
        commands, superuser_session, group, target_group)

    result = commands.group_remove_moderator(
        operator=superuser_session,
        lookup="{}".format(target_group.entity_id),
        dest_group="{}".format(group.entity_id),
    )

    assert result['group_id'] == group.entity_id
    assert result['moderator_id'] == target_group.entity_id
    assert result['group_type'] == 'manual-group'
    assert result['moderator_type'] == 'group'

    assert not GroupRoles.is_moderator(
        GroupRoles(group._db), target_group.entity_id, group.entity_id
    )


def test_bofhd_group_list_roles(
        commands, superuser_session, group, target_group):
    with pytest.raises(CerebrumError) as exception:
        commands.group_list_roles(
            operator=superuser_session,
            lookup="{}".format(target_group.entity_id),
        )
    assert 'has no group roles' in six.text_type(exception.value).lower()

    test_bofhd_group_add_admin(commands, superuser_session, group, target_group)
    test_bofhd_group_add_moderator(
        commands, superuser_session, group, target_group)

    result = commands.group_list_roles(
        operator=superuser_session,
        lookup="{}".format(target_group.entity_id),
    )
    assert len(result) == 2

    result = commands.group_list_roles(
        operator=superuser_session,
        lookup="{}".format(target_group.entity_id),
        role='admin',
    )
    assert len(result) == 1

    result = commands.group_list_roles(
        operator=superuser_session,
        lookup="{}".format(target_group.entity_id),
        role='moderator',
    )
    assert len(result) == 1


def test_bofhd_group_list_owners(
        commands, superuser_session, group, target_group):
    with pytest.raises(CerebrumError) as exception:
        commands.group_list_owners(
            operator=superuser_session,
            target="{}".format(group.entity_id),
        )
    assert 'has no admins/moderators' in six.text_type(exception.value).lower()

    test_bofhd_group_add_admin(commands, superuser_session, group, target_group)
    test_bofhd_group_add_moderator(
        commands, superuser_session, group, target_group)

    result = commands.group_list_owners(
        operator=superuser_session,
        target="{}".format(group.entity_id),
    )
    assert len(result) == 2

    result = commands.group_list_owners(
        operator=superuser_session,
        target="{}".format(group.entity_id),
        role='admin',
    )
    assert len(result) == 1

    result = commands.group_list_owners(
        operator=superuser_session,
        target="{}".format(group.entity_id),
        role='moderator',
    )
    assert len(result) == 1
