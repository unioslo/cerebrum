# encoding: utf-8
""" Tests for mod:`Cerebrum.modules.apikeys.bofhd_apikey_cmds` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

import pytest

from Cerebrum.group.template import GroupTemplate
from Cerebrum.modules.apikeys import bofhd_apikey_cmds
from Cerebrum.modules.apikeys import dbal
from Cerebrum.modules.bofhd import errors
from Cerebrum.modules.bofhd import session
from Cerebrum.testutils.log_utils import StrictNullHandler


@pytest.fixture
def logger(scope='module', autouse=True):
    """ a logger that also catches badly formatted log records. """
    logger = logging.getLogger("test")
    logger.addHandler(StrictNullHandler())
    logger.setLevel(-100)
    return logger


@pytest.fixture
def commands(database, logger):
    return bofhd_apikey_cmds.BofhdApiKeyCommands(database, logger)


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
def account_session(database, account):
    operator = session.BofhdSession(database)
    operator.set_authenticated_entity(account.entity_id, "127.0.0.1")
    return operator


@pytest.fixture
def apikeys(database):
    return dbal.ApiMapping(database)


#
# Test help strings
#


@pytest.mark.parametrize("group_name", ["api"])
def test_help_strings_group(commands, group_name):
    group, _, _ = commands.get_help_strings()
    assert group_name in group


@pytest.mark.parametrize(
    "command_name",
    [
        "api_subscription_set",
        "api_subscription_clear",
        "api_subscription_list",
        "api_subscription_info",
    ],
)
def test_help_strings_cmd(commands, command_name):
    _, cmds, _ = commands.get_help_strings()
    assert "api" in cmds
    cmd_group = cmds['api']
    assert command_name in cmd_group


@pytest.mark.parametrize(
    "arg_name",
    [
        "api-client-id",
        "api-client-desc",
    ],
)
def test_help_strings_args(commands, arg_name):
    _, _, args = commands.get_help_strings()
    assert arg_name in args


#
# Basic authz tests
#


def test_is_superuser(commands, superuser_session):
    operator_id = superuser_session.get_entity_id()
    assert commands.ba.is_superuser(operator_id)


def test_is_not_superuser(commands, account_session):
    operator_id = account_session.get_entity_id()
    assert not commands.ba.is_superuser(operator_id)


def test_can_modify_api_mapping_superuser(commands, superuser_session,
                                          account):
    operator_id = superuser_session.get_entity_id()
    assert commands.ba.can_modify_api_mapping(operator_id, query_run_any=True)
    assert commands.ba.can_modify_api_mapping(operator_id, account=account)


def test_can_modify_api_mapping_others(commands, account_session, account):
    operator_id = account_session.get_entity_id()
    assert not commands.ba.can_modify_api_mapping(operator_id,
                                                  query_run_any=True)
    with pytest.raises(errors.PermissionDenied):
        commands.ba.can_modify_api_mapping(operator_id, account=account)


def test_can_list_api_mapping_superuser(commands, superuser_session, account):
    operator_id = superuser_session.get_entity_id()
    assert commands.ba.can_list_api_mapping(operator_id, query_run_any=True)
    assert commands.ba.can_list_api_mapping(operator_id, account=account)


def test_can_list_api_mapping_others(commands, account_session, account):
    operator_id = account_session.get_entity_id()
    assert not commands.ba.can_list_api_mapping(operator_id,
                                                query_run_any=True)
    with pytest.raises(errors.PermissionDenied):
        commands.ba.can_list_api_mapping(operator_id, account=account)


#
# Basic command tests
#


IDENTIFIER_1 = "sub-1-cafde8bbf7444ebb"


def test_api_subscription_set(apikeys, commands, superuser_session, account):
    identifier = IDENTIFIER_1
    result = commands.api_subscription_set(
        operator=superuser_session,
        identifier=identifier,
        account_id="id:{}".format(account.entity_id),
    )

    assert result == {
        'identifier': identifier,
        'account_id': account.entity_id,
        'account_name': account.account_name,
        'description': None,
    }
    assert apikeys.exists(identifier)


def test_api_subscription_clear(apikeys, commands, superuser_session, account):
    identifier = IDENTIFIER_1
    description = "test subscription"
    apikeys.set(identifier, account.entity_id, description=description)

    result = commands.api_subscription_clear(
        operator=superuser_session,
        identifier=identifier,
    )

    assert result == {
        'identifier': identifier,
        'account_id': account.entity_id,
        'account_name': account.account_name,
        'description': description,
    }
    assert not apikeys.exists(identifier)


def test_api_subscription_list(apikeys, commands, superuser_session, account):
    identifier = IDENTIFIER_1
    description = "test subscription"
    apikeys.set(identifier, account.entity_id, description=description)

    results = commands.api_subscription_list(
        operator=superuser_session,
        account_id="id:{}".format(account.entity_id),
    )

    assert len(results) == 1
    result = results[0]
    assert result['identifier'] == identifier
    assert result['account_id'] == account.entity_id
    assert result['description'] == description


def test_api_subscription_info(apikeys, commands, superuser_session, account):
    identifier = IDENTIFIER_1
    description = "test subscription"
    apikeys.set(identifier, account.entity_id, description=description)

    result = commands.api_subscription_info(
        operator=superuser_session,
        identifier=identifier,
    )

    assert result['account_id'] == account.entity_id
    assert result['account_name'] == account.account_name
    assert result['identifier'] == identifier
    assert result['updated_at']
    assert result['description'] == description
