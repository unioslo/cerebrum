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

from Cerebrum.group.GroupRoles import GroupRoles
from Cerebrum.modules.bofhd import bofhd_mixins, bofhd_group_roles
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.Errors import NotFoundError


@pytest.fixture
def mixin_class():
    return bofhd_mixins.BofhdAuthEntityMixin


@pytest.fixture
def commands(database, logger):
    return bofhd_group_roles.BofhdGroupRoleCommands(database, logger)


@pytest.fixture
def group_2(group_creator):
    group, _ = next(group_creator(1))
    return group


def test_bofhd_auth_entity_mixin_delete(
        commands, mixin_class, superuser_session, group, group_2):
    # Test the mixin delete method that cleans group roles upon entity deletion
    roles = GroupRoles(group._db)

    roles.add_admin_to_group(int(group.entity_id), int(group_2.entity_id))
    roles.add_moderator_to_group(int(group_2.entity_id), int(group.entity_id))

    assert roles.is_admin(group.entity_id, group_2.entity_id)
    assert roles.is_moderator(group_2.entity_id, group.entity_id)

    result = commands.group_list_roles(
        operator=superuser_session,
        lookup="{}".format(group_2.entity_id),
    )
    assert len(result) == 1

    # Make sure the Group class actually implements the mixin class
    if not isinstance(group, mixin_class):
        pytest.skip("Group does not implement mixin")

    entity_id = group.entity_id
    group.delete()

    with pytest.raises(NotFoundError):
        group.find(entity_id)

    assert not roles.is_admin(entity_id, group_2.entity_id)
    assert not roles.is_moderator(group_2.entity_id, entity_id)

    with pytest.raises(CerebrumError) as exception:
        commands.group_list_roles(
            operator=superuser_session,
            lookup="{}".format(group_2.entity_id),
        )
    assert "has no group roles" in six.text_type(exception.value).lower()
